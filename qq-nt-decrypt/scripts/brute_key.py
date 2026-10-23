#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从内存扫描得到的候选 key 中暴力验证出真正的 QQ NT 解密 key。

QQ NT 数据库结构: 前 1024 字节是自定义头（魔数 "SQLite header 3" + "QQ_NT DB" +
protobuf 头），之后是 SQLCipher 加密区。
官方解密参数（实测）:
    cipher_page_size = 4096   (必须在 key 之前设置)
    key              = '<16字节ASCII>'
    kdf_iter         = 4000
    cipher_hmac_algorithm = HMAC_SHA1
    cipher_kdf_algorithm  = PBKDF2_HMAC_SHA512   (派生 32 字节密钥)

本脚本先剥离待测试库的 1024 字节头，得到 *_clear.db，再用上述 PRAGMA 序列逐个
候选尝试打开；第一个能成功执行 SELECT count(*) FROM sqlite_master 的即真 key，
写入 key 文件并退出。

用法:
    python brute_key.py --src nt_msg.db --cand qq_key_candidates.txt --key qq_key.txt
    python brute_key.py --src nt_msg.db --clear qq_out/nt_msg_clear.db \
                        --cand qq_key_candidates.txt --key qq_key.txt --workers 8
"""
import argparse
import os
import sqlcipher3
from concurrent.futures import ProcessPoolExecutor

HEADER_SIZE = 1024
PRAGMAS = [
    "PRAGMA cipher_page_size=4096",
    "PRAGMA kdf_iter=4000",
    "PRAGMA cipher_hmac_algorithm=HMAC_SHA1",
    "PRAGMA cipher_kdf_algorithm=PBKDF2_HMAC_SHA512",
]


def strip_header(src, dst):
    if os.path.abspath(src) == os.path.abspath(dst):
        return  # src 已是剥离后的 clear，无需再处理
    if dst.exists() and dst.stat().st_size == src.stat().st_size - HEADER_SIZE:
        return
    with open(src, "rb") as f:
        f.seek(HEADER_SIZE)
        with open(dst, "wb") as out:
            while chunk := f.read(64 << 20):
                out.write(chunk)


def try_key(con, k):
    try:
        cur = con.cursor()
        cur.execute("PRAGMA cipher_page_size=4096")
        cur.execute("PRAGMA key = '" + k.replace("'", "''") + "'")
        for p in PRAGMAS[1:]:
            cur.execute(p)
        cur.execute("SELECT count(*) FROM sqlite_master")
        n = cur.fetchone()[0]
        return n if n and n > 0 else 0
    except Exception:
        return 0


def worker(clear_path, shard, out_path):
    con = sqlcipher3.connect(str(clear_path))
    for k in shard:
        k = k.strip()
        if not k:
            continue
        n = try_key(con, k)
        if n > 0:
            with open(out_path, "w", encoding="latin-1") as f:
                f.write(k)
            con.close()
            return (k, n)
    con.close()
    return None


def main():
    ap = argparse.ArgumentParser(description="暴力验证 QQ NT 解密 key")
    ap.add_argument("--src", required=True, help="待解密的源库（如 nt_msg.db）")
    ap.add_argument("--clear", default=None, help="剥离头部后的中间文件（默认 <src>_clear.db）")
    ap.add_argument("--cand", required=True, help="候选 key 文件（每行一个）")
    ap.add_argument("--key", default="qq_key.txt", help="找到的 key 写出文件")
    ap.add_argument("--workers", type=int, default=0, help="并行进程数（默认=CPU核数）")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    clear = args.clear or (src + "_clear.db")
    clear = os.path.abspath(clear)

    print(f"[brute] 剥离 {os.path.basename(src)} 头部 -> {os.path.basename(clear)}")
    strip_header(__import__("pathlib").Path(src), __import__("pathlib").Path(clear))

    with open(args.cand, "r", encoding="latin-1") as f:
        cands = f.readlines()
    nproc = args.workers or min(8, os.cpu_count() or 4)
    size = (len(cands) + nproc - 1) // nproc
    shards = [cands[i * size:(i + 1) * size] for i in range(nproc)]
    print(f"[brute] {len(cands)} 候选, {nproc} 进程, 每进程 {size}")

    with ProcessPoolExecutor(max_workers=nproc) as ex:
        futs = [ex.submit(worker, clear, s, os.path.abspath(args.key)) for s in shards]
        for fut in futs:
            res = fut.result()
            if res:
                print(f"[brute] 命中 key={res[0]!r} 表数={res[1]}")
                for f in futs:
                    f.cancel()
                return
    print("[brute] 候选集中未找到 key（可能进程未登录/key不在内存/候选遗漏）")


if __name__ == "__main__":
    main()
