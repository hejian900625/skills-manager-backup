#!/usr/bin/env python3
"""[兼容保留] 从已 dump 的 blob 文件生成 all_keys.json。

**新代码请直接用 `extract_keys.py`** —— 它一步完成「进程内存扫描 + XOR 解码 + 校验 + 落盘」，
不需要先跑 dump_config_blobs.py。

本脚本保留给「blob 已经 dump 到磁盘、现在只想离线解析」的场景。

用法:
  python gen_keys.py --db-dir <db_storage> [--blob-dir <dir>] [--out <all_keys.json>]

注意: 旧版本此脚本硬编码了 E:\\微信\\... 和 C:/Users/Administrator/ 路径，且缺少
      XOR 解码步骤（在微信 4.1.13 上必然 0 命中）。现均已修正。
"""
import argparse
import glob
import json
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wcdb_key_tool_windows import collect_db_files, verify_enc_key, auto_detect_db_dir  # noqa: E402

XOR_MASK = bytes.fromhex(
    "d2c7442458020000004889442450488b450048844c2448488944254048584c24"
)


def xor_decode(data):
    return bytes(v ^ XOR_MASK[i % len(XOR_MASK)] for i, v in enumerate(data))


def main():
    ap = argparse.ArgumentParser(description="从 dump 的 blob 生成 all_keys.json")
    ap.add_argument("--db-dir", help="db_storage 目录（默认自动检测）")
    ap.add_argument("--blob-dir", default=os.path.join(tempfile.gettempdir(), "config_dump"),
                    help="blob 所在目录（默认 %%TEMP%%/config_dump）")
    ap.add_argument("--out", default=os.path.expanduser("~/.wechat-cli/all_keys.json"))
    args = ap.parse_args()

    db_dir = args.db_dir or auto_detect_db_dir()
    if not db_dir:
        print("[ERROR] 未指定 --db-dir 且自动检测失败")
        sys.exit(1)
    print(f"[*] db dir: {db_dir}")

    db_files, salt_to_dbs = collect_db_files(db_dir)
    page1 = {s: p for _r, _p, _z, s, p in db_files}
    rel = {s: r for r, _p, _z, s, _p1 in db_files}
    print(f"[*] db files: {len(db_files)}, salts: {len(salt_to_dbs)}")

    pattern = os.path.join(args.blob_dir, "*.bin")
    files = glob.glob(pattern)
    if not files:
        print(f"[ERROR] {args.blob_dir} 下没有 .bin 文件。")
        print("        先运行: python dump_config_blobs.py --dump-dir "
              f"\"{args.blob_dir}\"")
        print("        或直接用 extract_keys.py（推荐，一步到位）")
        sys.exit(1)
    print(f"[*] blob files: {len(files)}")

    # XOR 解码 -> x'<key64><salt32>'
    candidates = set()
    for fn in files:
        try:
            text = xor_decode(open(fn, "rb").read()).decode("ascii")
        except (UnicodeDecodeError, OSError):
            continue
        m = re.match(r"x'([0-9a-fA-F]{96})'", text.strip())
        if m:
            candidates.add(m.group(1).lower())

    found = {}
    for h in candidates:
        key, salt = bytes.fromhex(h[:64]), h[64:96]
        if salt in page1 and salt not in found and verify_enc_key(key, page1[salt]):
            found[salt] = h[:64]
            print(f"  [OK] {rel[salt]}")

    print(f"[*] matched {len(found)}/{len(salt_to_dbs)}")
    for s in salt_to_dbs:
        if s not in found:
            print(f"  MISSING: {rel[s]} (salt={s})")

    if not found:
        print("[!] 无命中：确认 blob 与 db_dir 属于同一账号，且 blob 未经 XOR 解码前不要直接匹配")
        sys.exit(1)

    result = {}
    for r, _p, z, s, _p1 in db_files:
        if s in found:
            result[r] = {"enc_key": found[s], "salt": s,
                         "size_mb": round(z / 1024 / 1024, 1)}
    result["_db_dir"] = db_dir

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[+] saved {len(result) - 1} keys -> {args.out}")


if __name__ == "__main__":
    main()
