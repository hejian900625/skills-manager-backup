#!/usr/bin/env python3
"""Dump WeChat Config.Cipher blobs from the running Weixin.exe process(es).

Produces the raw (XOR-obfuscated) 99-byte blobs that hold each database's
(enc_key, salt) hex pair.

Usage:
  python dump_config_blobs.py [--db-dir <db_storage>] [--dump-dir <dir>]

The --db-dir argument is used only to locate which databases we care about
(reported in the summary); the blobs themselves come from process memory.
When omitted, the data dir is auto-detected from the WeChat ini config.
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wcdb_key_tool_windows import (  # noqa: E402
    auto_detect_db_dir, WINDOWS_CONFIG_CIPHER_NAME,
    _find_bytes_in_regions, _iter_windows_region_chunks, _u64_from,
    WINDOWS_MAX_USER_ADDRESS, WINDOWS_CONFIG_BLOB_MAX,
)

kernel32 = ctypes.windll.kernel32
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_uint64), ("AllocationBase", ctypes.c_uint64),
        ("AllocationProtect", wt.DWORD), ("_pad1", wt.DWORD),
        ("RegionSize", ctypes.c_uint64), ("State", wt.DWORD),
        ("Protect", wt.DWORD), ("Type", wt.DWORD), ("_pad2", wt.DWORD),
    ]


def read_mem(h, addr, sz):
    buf = ctypes.create_string_buffer(sz)
    n = ctypes.c_size_t(0)
    if kernel32.ReadProcessMemory(h, ctypes.c_uint64(addr), buf, sz, ctypes.byref(n)):
        return buf.raw[: n.value]
    return None


def enum_regions(h):
    regs, addr, mbi = [], 0, MBI()
    while addr < 0x7FFFFFFFFFFF:
        if kernel32.VirtualQueryEx(h, ctypes.c_uint64(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0:
            break
        if mbi.State == MEM_COMMIT and mbi.Protect in READABLE and 0 < mbi.RegionSize < 500 * 1024 * 1024:
            regs.append((mbi.BaseAddress, mbi.RegionSize))
        nxt = mbi.BaseAddress + mbi.RegionSize
        if nxt <= addr:
            break
        addr = nxt
    return regs


def get_pids():
    r = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, errors="replace", encoding="mbcs",
    )
    pids = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        p = line.strip('"').split('","')
        if len(p) >= 5:
            pids.append((int(p[1]), int(p[4].replace(",", "").replace(" K", "").strip() or "0")))
    pids.sort(key=lambda x: x[1], reverse=True)
    return pids


def main():
    ap = argparse.ArgumentParser(description="Dump WeChat Config.Cipher blobs")
    ap.add_argument("--db-dir", help="微信 db_storage 目录（默认自动检测）")
    ap.add_argument("--dump-dir",
                    default=os.path.join(tempfile.gettempdir(), "config_dump"),
                    help="blob 输出目录（默认 %%TEMP%%/config_dump）")
    ap.add_argument("--json", metavar="PATH",
                    help="同时导出 key/salt 候选 JSON（需配合 wechat_key_xor.py）")
    args = ap.parse_args()

    db_dir = args.db_dir or auto_detect_db_dir()
    if db_dir:
        print(f"[*] db dir: {db_dir}")
        try:
            from wcdb_key_tool_windows import collect_db_files
            db_files, salt_to_dbs = collect_db_files(db_dir)
            print(f"[*] db files: {len(db_files)}, salts: {len(salt_to_dbs)}")
        except Exception as e:
            print(f"[!] 读取 db 目录失败: {e}")
    else:
        print("[!] 未指定 --db-dir 且自动检测失败（仅 dump blob，不做 db 匹配）")

    os.makedirs(args.dump_dir, exist_ok=True)

    pids = get_pids()
    if not pids:
        print("[ERROR] Weixin.exe 未运行，请先启动并登录微信")
        sys.exit(1)

    blobs = []
    seen = set()
    for pid, mem_kb in pids:
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            print(f"[WARN] 无法打开进程 PID={pid}（尝试以管理员身份运行）")
            continue
        try:
            regions = enum_regions(h)
            addrs = _find_bytes_in_regions(
                regions, lambda b, s, _h=h: read_mem(_h, b, s), WINDOWS_CONFIG_CIPHER_NAME)
            print(f"[*] pid={pid} ({mem_kb // 1024}MB) needle occurrences: {len(addrs)}")
            if not addrs:
                continue
            pats = [struct.pack("<Q", a) + struct.pack("<Q", len(WINDOWS_CONFIG_CIPHER_NAME))
                    for a in addrs]
            for base, data in _iter_windows_region_chunks(
                    regions, lambda b, s, _h=h: read_mem(_h, b, s), overlap=0x80):
                for pat in pats:
                    pos = data.find(pat)
                    while pos >= 0:
                        node = read_mem(h, base + pos - 0x10, 0x50)
                        if node and len(node) >= 0x40 \
                                and _u64_from(node, 0x10) in addrs \
                                and _u64_from(node, 0x18) == len(WINDOWS_CONFIG_CIPHER_NAME):
                            cptr = _u64_from(node, 0x28)
                            if 0x10000 <= cptr < WINDOWS_MAX_USER_ADDRESS:
                                obj = read_mem(h, cptr + 0x88, 0x28)
                                if obj and len(obj) >= 0x18:
                                    dptr, dlen = _u64_from(obj, 0x8), _u64_from(obj, 0x10)
                                    if 0 < dlen <= WINDOWS_CONFIG_BLOB_MAX \
                                            and 0x10000 <= dptr < WINDOWS_MAX_USER_ADDRESS:
                                        blob = read_mem(h, dptr, int(dlen))
                                        if blob and len(blob) == dlen and blob not in seen:
                                            seen.add(blob)
                                            blobs.append((pid, cptr, dlen, blob))
                        pos = data.find(pat, pos + 1)
        finally:
            kernel32.CloseHandle(h)

    print(f"[*] unique blobs: {len(blobs)}")
    for i, (pid, cptr, dlen, blob) in enumerate(blobs):
        fn = os.path.join(args.dump_dir, f"blob_{i:03d}_pid{pid}_ptr{cptr:x}_len{dlen}.bin")
        with open(fn, "wb") as f:
            f.write(blob)
    print(f"[+] dumped {len(blobs)} blobs -> {args.dump_dir}")

    if args.json:
        import json
        info = [{"pid": pid, "ptr": f"{cptr:x}", "len": dlen, "hex": blob.hex()}
                for pid, cptr, dlen, blob in blobs]
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
        print(f"[+] blob metadata -> {args.json}")

    print("\n下一步: python wechat_key_xor.py --db-dir \"<db_storage>\"")
    print("  注意：blob 是 XOR 混淆的，必须经 wechat_key_xor.py 解码后才能拿到密钥。")


if __name__ == "__main__":
    main()
