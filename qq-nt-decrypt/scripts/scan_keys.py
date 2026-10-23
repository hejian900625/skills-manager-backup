#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描正在运行的 QQ.exe 进程内存，提取 16 字节可打印 ASCII 候选 key。

QQ NT 的解密 key 是一个 16 字节 ASCII 字符串，明文驻留在 QQ.exe 进程内存中
（由 nt_sqlite3_key_v2 调用时写入）。本脚本枚举进程可写提交内存，用边界精确的
正则提取所有 16 字节可打印串作为候选，供 brute_key.py 后续验证。

用法:
    python scan_keys.py --out qq_key_candidates.txt
    python scan_keys.py --pid 18768 --out candidates.txt
"""
import argparse
import ctypes
import ctypes.wintypes
import os
import re
import subprocess
import sys
import time

MEM_COMMIT = 0x1000
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE_READWRITE = 0x40
PAGE_EXECUTE_WRITECOPY = 0x80
WRITABLE = {PAGE_READWRITE, PAGE_WRITECOPY, PAGE_EXECUTE_READWRITE, PAGE_EXECUTE_WRITECOPY}

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.wintypes.DWORD),
        ("PartitionId", ctypes.wintypes.WORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.wintypes.DWORD),
        ("Protect", ctypes.wintypes.DWORD),
        ("Type", ctypes.wintypes.DWORD),
    ]


def find_qq_pid():
    """通过 tasklist 定位 QQ.exe 的 PID（取第一个）。"""
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq QQ.exe", "/FO", "CSV"],
            text=True, stderr=subprocess.DEVNULL,
        )
    except Exception:
        return None
    for line in out.splitlines()[1:]:
        if "QQ.exe" in line:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) >= 2 and parts[0].lower() == "qq.exe":
                try:
                    return int(parts[1])
                except ValueError:
                    continue
    return None


def main():
    ap = argparse.ArgumentParser(description="扫描 QQ.exe 内存提取候选 key")
    ap.add_argument("--pid", type=int, default=0, help="QQ.exe PID（默认自动探测）")
    ap.add_argument("--out", default="qq_key_candidates.txt", help="候选 key 输出文件")
    args = ap.parse_args()

    pid = args.pid or find_qq_pid()
    if not pid:
        print("未找到运行中的 QQ.exe，请先登录 QQ NT 后再运行。", file=sys.stderr)
        sys.exit(2)
    print(f"[scan] 目标 PID = {pid}")

    kernel32 = ctypes.windll.kernel32
    hProc = kernel32.OpenProcess(0x10 | 0x400, False, pid)  # VM_READ | QUERY_INFORMATION
    if not hProc:
        print("OpenProcess 失败, 错误码:", kernel32.GetLastError(), file=sys.stderr)
        sys.exit(1)

    mbi = MEMORY_BASIC_INFORMATION()
    addr = 0
    MAX_ADDR = 0x7FFFFFFFFFFF
    candidates = set()
    run_re = re.compile(rb"[ -~]+")
    bounded_re = re.compile(rb"(?<![ -~])[ -~]{16}(?![ -~])")
    region_count = 0
    byte_count = 0
    t0 = time.time()

    while addr < MAX_ADDR:
        ret = kernel32.VirtualQueryEx(hProc, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if ret == 0:
            addr = (addr + 0x10000) & ~0xFFFF
            if addr <= 0:
                break
            continue
        base = addr
        size = mbi.RegionSize
        if mbi.State == MEM_COMMIT and mbi.Protect in WRITABLE and size <= 512 * 1024 * 1024:
            buf = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t()
            ok = kernel32.ReadProcessMemory(hProc, ctypes.c_void_p(base), buf, size, ctypes.byref(read))
            if ok and read.value > 0:
                data = bytes(buf[:read.value])
                byte_count += len(data)
                region_count += 1
                for m in bounded_re.finditer(data):
                    candidates.add(m.group(0))
                for m in run_re.finditer(data):
                    r = m.group(0)
                    if len(r) == 16:
                        candidates.add(r)
                    elif len(r) > 16:
                        candidates.add(r[:16])
                        candidates.add(r[-16:])
        nxt = base + size
        if nxt <= addr:
            addr = (addr + 0x10000) & ~0xFFFF
        else:
            addr = nxt

    print(f"[scan] 扫描完成: 区域={region_count} 读取={byte_count/1024/1024:.1f}MB "
          f"候选={len(candidates)} 用时={time.time()-t0:.1f}s")
    with open(args.out, "w", encoding="latin-1") as f:
        for c in sorted(candidates):
            f.write(c.decode("latin-1") + "\n")
    print(f"[scan] 已写出: {args.out}")


if __name__ == "__main__":
    main()
