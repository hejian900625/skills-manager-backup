#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用找到的 key 将 QQ NT 目录下所有数据库解密为明文 SQLite。

流程（对每个 *.db）:
    1. 剥离前 1024 字节自定义头 -> <name>_clear.db
    2. 用 key + 固定 PRAGMA 序列打开加密区 -> <name>_plain.db
    3. 逐表游标导出（绕开 rowid，对损坏行降级单行插入），FTS/pinyin 自定义分词器
       表失败不影响其它表。

KDF: PBKDF2_HMAC_SHA512, 4000 轮, 32 字节密钥; HMAC_SHA1; page_size 4096。

用法:
    python decrypt_all.py --srcdir "C:/Users/x/Documents/Tencent Files/123/nt_qq/nt_db" \
                         --outdir qq_out --key qq_key.txt
"""
import argparse
import datetime
import os
import pathlib
import re
import sqlite3
import time

import sqlcipher3.dbapi2 as sc

HEADER_SIZE = 1024
INTERNAL = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat2", "sqlite_stat3", "sqlite_stat4"}


def log(path, *a):
    line = " ".join(str(x) for x in a)
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now():%H:%M:%S}] {line}\n")


def load_key(path):
    with open(path, "r", encoding="latin-1") as f:
        return f.read().strip()


def strip_header(src, dst):
    expected = src.stat().st_size - HEADER_SIZE
    if dst.exists() and dst.stat().st_size == expected:
        return
    with open(src, "rb") as f:
        f.seek(HEADER_SIZE)
        with open(dst, "wb") as out:
            while chunk := f.read(64 << 20):
                out.write(chunk)
    log(LOG, f"  strip_header -> {dst.name} ({dst.stat().st_size/1024/1024:.1f}MB)")


def open_enc(path, key):
    conn = sc.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA cipher_page_size = 4096;")
    conn.execute(f"PRAGMA key = '{key.replace(chr(39), chr(39)*2)}';")
    conn.execute("PRAGMA kdf_iter = 4000;")
    conn.execute("PRAGMA cipher_hmac_algorithm = HMAC_SHA1;")
    conn.execute("PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;")
    conn.execute("SELECT count(*) FROM sqlite_master;").fetchone()
    return conn


def export_table(enc, plain, table, key):
    ddl = enc.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not ddl or not ddl[0]:
        return 0, 0
    ddl_safe = re.sub(r"^CREATE\s+TABLE\s+", "CREATE TABLE IF NOT EXISTS ", ddl[0], flags=re.IGNORECASE)
    plain.execute(ddl_safe); plain.commit()
    cols = enc.execute(f'PRAGMA table_info("{table}")').fetchall()
    ncols = len(cols)
    if ncols == 0:
        return 0, 0
    ph = ",".join("?" * ncols)
    ok = 0; bad = 0; batch = 5000
    cur = enc.execute(f'SELECT * FROM "{table}"')
    while True:
        rows = cur.fetchmany(batch)
        if not rows:
            break
        try:
            plain.executemany(f'INSERT OR IGNORE INTO "{table}" VALUES ({ph})', rows)
            plain.commit()
            ok += len(rows)
        except Exception:
            for r in rows:
                try:
                    plain.execute(f'INSERT OR IGNORE INTO "{table}" VALUES ({ph})', r)
                    ok += 1
                except Exception:
                    bad += 1
            plain.commit()
    del cur
    return ok, bad


LOG = ""


def main():
    global LOG
    ap = argparse.ArgumentParser(description="解密 QQ NT 全部数据库")
    ap.add_argument("--srcdir", required=True, help="nt_db 目录（含 *.db）")
    ap.add_argument("--outdir", default="qq_out", help="解密输出目录")
    ap.add_argument("--key", default="qq_key.txt", help="key 文件路径")
    ap.add_argument("--log", default=None, help="日志文件（默认 <outdir>/qq_decrypt.log）")
    args = ap.parse_args()

    OUT = pathlib.Path(args.outdir)
    OUT.mkdir(parents=True, exist_ok=True)
    LOG = args.log or str(OUT / "qq_decrypt.log")
    open(LOG, "w", encoding="utf-8").close()

    key = load_key(args.key)
    log(LOG, f"使用 key: {key!r}")
    src = pathlib.Path(args.srcdir)
    dbs = sorted([p for p in src.glob("*.db") if not p.name.endswith((".db-wal", ".db-shm", ".db-journal"))])
    log(LOG, f"待解密数据库: {len(dbs)}")
    t_all = time.time()
    total_ok = total_bad = 0
    for i, db in enumerate(dbs, 1):
        if db.stat().st_size <= HEADER_SIZE:
            log(LOG, f"[{i}/{len(dbs)}] {db.name}: 太小(<=1024B)，跳过")
            continue
        log(LOG, f"[{i}/{len(dbs)}] {db.name} 开始 ...")
        clear = OUT / f"{db.stem}_clear.db"
        plain = OUT / f"{db.stem}_plain.db"
        try:
            t0 = time.time()
            strip_header(db, clear)
            enc = open_enc(clear, key)
            tables = [r[0] for r in enc.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
            enc.close()
            p = sqlite3.connect(str(plain))
            p.execute("PRAGMA journal_mode=WAL;"); p.execute("PRAGMA synchronous=NORMAL;")
            ok = bad = 0
            for t in tables:
                if t in INTERNAL:
                    continue
                try:
                    o, b = export_table(open_enc(clear, key), p, t, key)
                    ok += o; bad += b
                    log(LOG, f"    [{db.name}] 表 {t}: +{o:,} 跳{b}")
                except Exception as e:
                    log(LOG, f"    表 {t} 失败: {e}")
            try:
                e2 = open_enc(clear, key)
                for (ddl,) in e2.execute(
                        "SELECT sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL").fetchall():
                    try: p.execute(ddl)
                    except Exception: pass
                e2.close()
            except Exception: pass
            p.commit(); p.close()
            total_ok += ok; total_bad += bad
            log(LOG, f"  ✓ {db.name}: {ok:,} 行, 跳过 {bad}, 输出 {plain.name} "
                     f"({plain.stat().st_size/1024/1024:.1f}MB) 用时 {time.time()-t0:.0f}s")
        except Exception as e:
            log(LOG, f"  ✗ {db.name} 解密失败: {e}")
    log(LOG, f"=== 全部完成: {total_ok:,} 行, 跳过 {total_bad} 处, 总用时 {time.time()-t_all:.0f}s ===")
    print(f"[decrypt_all] 完成，详见 {LOG}")


if __name__ == "__main__":
    main()
