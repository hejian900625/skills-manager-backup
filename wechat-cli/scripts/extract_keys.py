"""微信 4.1.13+ 密钥提取（XOR 解码版，通用参数化）。

用法:
  python extract_keys.py --db-dir <db_storage目录> [--out <all_keys.json>] [--config <config.json>]

原理（2026-09-29 实测于微信 4.1.13.65，21/21 库成功）:
  1. 从 Weixin.exe 进程内存定位 com.Tencent.WCDB.Config.Cipher 对象，dump 其 99 字节 blob
  2. blob 不是明文，而是被 XOR_MASK 混淆的 ASCII:  x'<enc_key 64hex><salt 32hex>'
  3. 前 32 字节（64 hex）**直接就是该库的 SQLCipher AES-256 密钥**，无需 PBKDF2
  4. 用 HMAC 对比 blob 内嵌的 salt 与目标库 page1 的 salt，校验通过才保存

注意:
  - 必须当前登录账号 == 目标 db_storage 账号（密钥属于登录中的账号）
  - 微信必须正在运行且已登录
  - 读取自己用户启动的微信进程不需要管理员权限（实测非管理员可成功）
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import re
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wcdb_key_tool_windows import (  # noqa: E402
    collect_db_files, verify_enc_key, auto_detect_db_dir,
    WINDOWS_CONFIG_CIPHER_NAME, _find_bytes_in_regions,
    _iter_windows_region_chunks, _u64_from,
    WINDOWS_MAX_USER_ADDRESS, WINDOWS_CONFIG_BLOB_MAX,
)

kernel32 = ctypes.windll.kernel32
MEM_COMMIT = 0x1000
READABLE = {0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}

# Config.Cipher blob 的 XOR 混淆掩码（微信 4.1.13）
XOR_MASK = bytes.fromhex(
    "d2c7442458020000004889442450488b450048844c2448488944254048584c24"
)


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


def xor_decode(data):
    """解开 Config.Cipher blob 的 XOR 混淆。"""
    return bytes(v ^ XOR_MASK[i % len(XOR_MASK)] for i, v in enumerate(data))


def find_blobs():
    """从 Weixin.exe 进程内存读取全部 Config.Cipher blob。"""
    blobs = []
    for pid, mem_kb in get_pids():
        h = kernel32.OpenProcess(0x0010 | 0x0400, False, pid)
        if not h:
            print(f"[WARN] 无法打开进程 PID={pid}")
            continue
        try:
            regions = enum_regions(h)
            addrs = _find_bytes_in_regions(
                regions, lambda b, s, _h=h: read_mem(_h, b, s), WINDOWS_CONFIG_CIPHER_NAME)
            print(f"[*] pid={pid} ({mem_kb // 1024}MB) needle hits: {len(addrs)}")
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
                                        if blob and len(blob) == dlen:
                                            blobs.append(blob)
                        pos = data.find(pat, pos + 1)
        finally:
            kernel32.CloseHandle(h)
    return blobs


def parse_key_salt(blob):
    """XOR 解码后按 x'<key64><salt32>' 取出 (enc_key, salt) 十六进制。"""
    try:
        text = xor_decode(blob).decode("ascii").strip()
    except UnicodeDecodeError:
        return None, None
    m = re.match(r"x'([0-9a-fA-F]{96})'", text)
    if not m:
        return None, None
    h = m.group(1).lower()
    return h[:64], h[64:96]


def main():
    ap = argparse.ArgumentParser(description="微信数据库密钥提取（4.1.13+ XOR 路线）")
    ap.add_argument("--db-dir", help="db_storage 目录（默认自动检测）")
    ap.add_argument("--out", default=os.path.expanduser("~/.wechat-cli/all_keys.json"))
    ap.add_argument("--config", help="同时写入 config.json（默认写到 --out 同目录）")
    ap.add_argument("--no-config", action="store_true", help="不写 config.json")
    args = ap.parse_args()

    db_dir = args.db_dir or auto_detect_db_dir()
    if not db_dir:
        print("[ERROR] 未指定 --db-dir 且自动检测失败，请手动指定 db_storage 路径")
        sys.exit(1)
    print(f"[*] db dir: {db_dir}")

    db_files, salt_to_dbs = collect_db_files(db_dir)
    if not db_files:
        print(f"[ERROR] 在 {db_dir} 未找到 .db 文件")
        sys.exit(1)
    page1 = {s: p for _r, _p, _z, s, p in db_files}
    rel = {s: r for r, _p, _z, s, _p1 in db_files}
    print(f"[*] db files: {len(db_files)}, salts: {len(salt_to_dbs)}")

    blobs = find_blobs()
    print(f"[*] blobs: {len(blobs)}")
    if not blobs:
        print("[ERROR] 未读到 Config.Cipher blob。请确认微信正在运行且已登录，"
              "且当前登录账号与 --db-dir 一致。")
        sys.exit(1)

    found = {}
    for blob in blobs:
        key_hex, salt = parse_key_salt(blob)
        if not key_hex or salt not in page1 or salt in found:
            continue
        if verify_enc_key(bytes.fromhex(key_hex), page1[salt]):
            found[salt] = key_hex
            print(f"  [OK] {rel[salt]}")

    print(f"[*] matched {len(found)}/{len(salt_to_dbs)}")
    for s in salt_to_dbs:
        if s not in found:
            print(f"  MISSING: {rel[s]} (salt={s})")

    if not found:
        print("[!] 无命中：确认当前登录账号 == 目标 db_dir，或微信重启后重试")
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

    if not args.no_config:
        cfg_path = args.config or os.path.join(os.path.dirname(os.path.abspath(args.out)),
                                               "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"db_dir": db_dir}, f, indent=2, ensure_ascii=False)
        print(f"[+] config -> {cfg_path}")


if __name__ == "__main__":
    main()
