#!/usr/bin/env python3
"""微信 4.1.13+ 密钥提取（XOR 解码版）

关键差异 vs skill 自带脚本：
  Config.Cipher blob 不是明文，而是 **XOR(d2c7442458020000004889442450488b450048844c2448488944254048584c24)**
  混淆后的 ASCII 字符串：  x'<enc_key 64hex><salt 32hex>'
  前 32 字节直接就是 AES 密钥，**不需要 PBKDF2**。

用法:
  python wechat_key_xor.py --db-dir <db_storage> [--out ~/.wechat-cli/all_keys.json]
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import glob
import json
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, r"C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts")
from wcdb_key_tool_windows import (  # noqa: E402
    collect_db_files, verify_enc_key, WINDOWS_CONFIG_CIPHER_NAME,
    _find_bytes_in_regions, _iter_windows_region_chunks, _u64_from,
    WINDOWS_MAX_USER_ADDRESS, WINDOWS_CONFIG_BLOB_MAX,
)

XOR_MASK = bytes.fromhex(
    "d2c7442458020000004889442450488b450048844c2448488944254048584c24"
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
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True, errors="replace", encoding="mbcs")
    pids = []
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        p = line.strip('"').split('","')
        if len(p) >= 5:
            pids.append((int(p[1]), int(p[4].replace(",", "").replace(" K", "").strip() or "0")))
    pids.sort(key=lambda x: x[1], reverse=True)
    return pids


def xor(data):
    return bytes(v ^ XOR_MASK[i % len(XOR_MASK)] for i, v in enumerate(data))


def dump_blobs():
    """从微信进程内存读出全部 Config.Cipher blob。"""
    blobs = []
    for pid, mem_kb in get_pids():
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            continue
        try:
            regions = enum_regions(h)
            addrs = _find_bytes_in_regions(
                regions, lambda b, s, _h=h: read_mem(_h, b, s), WINDOWS_CONFIG_CIPHER_NAME)
            if not addrs:
                continue
            pats = [struct.pack("<Q", a) + struct.pack("<Q", len(WINDOWS_CONFIG_CIPHER_NAME)) for a in addrs]
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
                                    if 0 < dlen <= WINDOWS_CONFIG_BLOB_MAX and 0x10000 <= dptr < WINDOWS_MAX_USER_ADDRESS:
                                        blob = read_mem(h, dptr, int(dlen))
                                        if blob and len(blob) == dlen:
                                            blobs.append(blob)
                        pos = data.find(pat, pos + 1)
        finally:
            kernel32.CloseHandle(h)
    return blobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", required=True)
    ap.add_argument("--out", default=os.path.expanduser("~/.wechat-cli/all_keys.json"))
    args = ap.parse_args()

    db_files, salt_to_dbs = collect_db_files(args.db_dir)
    page1 = {s: p for _r, _p, _z, s, p in db_files}
    rel = {s: r for r, _p, _z, s, _p1 in db_files}
    print(f"[*] db files: {len(db_files)}, salts: {len(salt_to_dbs)}")

    blobs = dump_blobs()
    print(f"[*] blobs: {len(blobs)}")

    found = {}
    for blob in blobs:
        try:
            text = xor(blob).decode("ascii")
        except UnicodeDecodeError:
            continue
        m = re.match(r"x'([0-9a-fA-F]{96})'", text.strip())
        if not m:
            continue
        h = m.group(1).lower()
        key, salt = bytes.fromhex(h[:64]), h[64:96]
        if salt in page1 and salt not in found and verify_enc_key(key, page1[salt]):
            found[salt] = h[:64]
            print(f"  [OK] {rel.get(salt, salt)}")

    print(f"[*] matched {len(found)}/{len(salt_to_dbs)}")
    for s in salt_to_dbs:
        if s not in found:
            print(f"  MISSING: {rel[s]}")

    if not found:
        print("[!] 无命中：确认微信已登录且当前账号 == 目标 db_dir")
        sys.exit(1)

    result = {}
    for r, _p, z, s, _p1 in db_files:
        if s in found:
            result[r] = {"enc_key": found[s], "salt": s, "size_mb": round(z / 1024 / 1024, 1)}
    result["_db_dir"] = args.db_dir
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[+] saved {len(result) - 1} keys -> {args.out}")


if __name__ == "__main__":
    main()
