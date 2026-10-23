#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ NT 聊天记录解密导出 —— 一键流水线。

自动完成:
    1. 探测运行中的 QQ.exe PID 与 nt_db 数据目录
    2. 扫描进程内存提取候选 key
    3. 用 sqlcipher3 并行暴力验证出真 key
    4. 解密 nt_db 下所有数据库
    5. 解析 protobuf 内容 + 群名映射，导出 CSV + HTML

依赖（本机托管 Python 环境已装）:  pip install sqlcipher3
（Windows 需要 sqlcipher3 的预编译 wheel，cp313 win_amd64 版本已在托管环境验证可用）

用法:
    python run_all.py                 # 全部默认，输出到 ./qq_out
    python run_all.py --outdir D:/qq_export
    python run_all.py --qqdir "C:/Users/x/Documents/Tencent Files/123"   # 跳过自动探测
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find_qq_pid():
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


def find_nt_db(qqdir=None):
    if qqdir:
        cand = os.path.join(qqdir, "nt_qq", "nt_db")
        if os.path.isdir(cand):
            return cand
    base = os.path.expanduser("~/Documents/Tencent Files")
    if os.path.isdir(base):
        for entry in sorted(os.listdir(base)):
            cand = os.path.join(base, entry, "nt_qq", "nt_db")
            if os.path.isdir(cand):
                return cand
    return None


def run(py, script, *cli):
    cmd = [py, os.path.join(HERE, script), *cli]
    print("\n$ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"[run_all] {script} 失败 (exit {r.returncode})", file=sys.stderr)
        sys.exit(r.returncode)


def main():
    ap = argparse.ArgumentParser(description="QQ NT 聊天记录一键解密导出")
    ap.add_argument("--qqdir", default=None, help="QQ 账号目录（含 nt_qq/nt_db），默认自动探测")
    ap.add_argument("--outdir", default="qq_out", help="输出目录")
    ap.add_argument("--srcdb", default="nt_msg.db", help="用于验证 key 的主库名")
    ap.add_argument("--workers", type=int, default=0, help="暴力 key 并行进程数")
    ap.add_argument("--skip-scan", action="store_true", help="复用已有 qq_key_candidates.txt")
    ap.add_argument("--skip-brute", action="store_true", help="复用已有 qq_key.txt")
    args = ap.parse_args()

    py = sys.executable
    outdir = os.path.abspath(args.outdir)
    os.makedirs(outdir, exist_ok=True)

    # 1. 探测
    pid = find_qq_pid()
    if not pid:
        print("[run_all] 未找到运行中的 QQ.exe，请先登录 QQ NT。", file=sys.stderr)
        sys.exit(2)
    print(f"[run_all] 探测到 QQ.exe PID={pid}")
    nt_db = find_nt_db(args.qqdir)
    if not nt_db:
        print("[run_all] 未找到 nt_db 目录，请用 --qqdir 指定。", file=sys.stderr)
        sys.exit(2)
    print(f"[run_all] nt_db 目录: {nt_db}")

    cand = os.path.join(outdir, "qq_key_candidates.txt")
    keyf = os.path.join(outdir, "qq_key.txt")

    # 2. 扫描内存
    if args.skip_scan and os.path.exists(cand):
        print(f"[run_all] 复用候选文件: {cand}")
    else:
        run(py, "scan_keys.py", "--pid", str(pid), "--out", cand)

    # 3. 暴力 key
    if args.skip_brute and os.path.exists(keyf):
        print(f"[run_all] 复用 key 文件: {keyf}")
    else:
        src = os.path.join(nt_db, args.srcdb)
        cli = ["--src", src, "--cand", cand, "--key", keyf, "--clear", os.path.join(outdir, "nt_msg_clear.db")]
        if args.workers:
            cli += ["--workers", str(args.workers)]
        run(py, "brute_key.py", *cli)
        if not os.path.exists(keyf):
            print("[run_all] 未找到 key，解密终止。", file=sys.stderr)
            sys.exit(3)

    # 4. 解密全部库
    run(py, "decrypt_all.py", "--srcdir", nt_db, "--outdir", outdir, "--key", keyf)

    # 5. 导出聊天记录
    run(py, "export_chats.py", "--outdir", outdir)

    print(f"\n[run_all] 完成。产物在: {outdir}")
    print(f"  - {os.path.join(outdir, 'qq_messages.csv')}")
    print(f"  - {os.path.join(outdir, 'qq_chat.html')}")


if __name__ == "__main__":
    main()
