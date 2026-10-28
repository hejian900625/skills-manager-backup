# -*- coding: utf-8 -*-
"""
给指定 Node 大版本装一份独立的 chatlab-cli 副本，绕开「某个 Node 上 clb 原生崩溃 / ABI 不匹配」。

背景:
  chatlab-cli 依赖原生模块 better-sqlite3，只能被「编译它时的那个 Node ABI」加载。
  如果全局那份是在 Node 24 下装的，而 clb 在 Node 24 上会崩溃（parsing 100% 后断言 abort），
  这台机器就没有可用的组合了。解决办法是用另一个 Node 大版本装一份独立副本，
  import_chatlab.py 会自动发现（find_clb_instances）并优先使用能跑通的那份。

用法:
  python setup_alt_clb.py [--node-major 22] [--node <node.exe>] [--dir <安装目录>]
                          [--version 0.37.5] [--dry-run]

默认装到 ~/.chatlab/clb-node<major>，不动全局安装，也不需要管理员权限。
"""
import sys, os, json, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _clb_common import (  # noqa: E402
    node_candidates, find_npm_cli, find_clb_js, clb_version,
    node_can_load_sqlite, run_clb, clb_crashed, parse_json_envelope,
    resolve_data_dir,
)


def pick_node(major):
    """挑一个指定大版本的 node.exe。"""
    for n in node_candidates():
        try:
            v = subprocess.run([n, "-v"], capture_output=True, text=True, timeout=15).stdout.strip()
        except Exception:
            continue
        if v.lstrip("v").split(".")[0] == str(major):
            return n, v
    return None, None


def main():
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        return
    major, node, target, version, dry = 22, None, None, None, False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--dry-run":
            dry = True; i += 1; continue
        if a.startswith("--") and "=" in a:
            k, v = a.split("=", 1)
            if k == "--node-major":
                major = int(v)
            elif k == "--node":
                node = v
            elif k == "--dir":
                target = v
            elif k == "--version":
                version = v
            else:
                print("[X] 未知参数:", k); sys.exit(1)
            i += 1; continue
        if a in ("--node-major", "--node", "--dir", "--version"):
            if i + 1 >= len(args):
                print("[X]", a, "缺少参数值"); sys.exit(1)
            v = args[i + 1]
            if a == "--node-major":
                major = int(v)
            elif a == "--node":
                node = v
            elif a == "--dir":
                target = v
            else:
                version = v
            i += 2; continue
        print("[X] 未知参数:", a); sys.exit(1)

    if node:
        if not os.path.isfile(node):
            print("[X] node 不存在:", node); sys.exit(1)
        nv = subprocess.run([node, "-v"], capture_output=True, text=True).stdout.strip()
    else:
        node, nv = pick_node(major)
        if not node:
            print("[X] 找不到 Node %d.x。可用 candidates:" % major)
            for n in node_candidates():
                print("     ", n)
            print("    可用 install_binary 装一个，或用 --node 指定绝对路径。")
            sys.exit(1)
    print("[i] node :", node, nv)

    npm = find_npm_cli()
    if not npm:
        print("[X] 找不到 npm-cli.js"); sys.exit(1)
    print("[i] npm  :", npm)

    if not version:
        version = clb_version(find_clb_js() or "") or "latest"
    print("[i] 版本 :", version)

    target = os.path.abspath(os.path.expanduser(target or "~/.chatlab/clb-node%d" % major))
    js = os.path.join(target, "node_modules", "chatlab-cli", "bin", "chatlab.mjs")
    print("[i] 目录 :", target)

    if os.path.isfile(js) and node_can_load_sqlite(node, js):
        print("[i] 该目录已有一份可用副本，跳过安装。")
    else:
        os.makedirs(target, exist_ok=True)
        cmd = [node, npm, "install", "chatlab-cli@" + version,
               "--no-audit", "--no-fund", "--loglevel=error"]
        print("[i] 执行 :", " ".join(cmd))
        if dry:
            print("[i] --dry-run，仅打印命令，不安装。")
            return
        r = subprocess.run(cmd, cwd=target, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if out:
            print(out[-1200:])
        if r.returncode != 0:
            print("[X] npm install 失败（exit %d）" % r.returncode); sys.exit(1)
        if not os.path.isfile(js):
            print("[X] npm 报安装成功，但目录里没有 chatlab-cli：", js)
            print("    常见于沙箱/受限环境——目标目录不在可写范围，npm 的写入被静默丢弃。")
            print("    改到可写目录重试： --dir <路径>，或设 CHATLAB_CLB_ALT_DIR 指向它；")
            print("    也可以在可写目录装好后整体搬过来。")
            sys.exit(1)

    # --- 验证：ABI 能加载 + 真跑一次 sessions list 不崩溃
    if not node_can_load_sqlite(node, js):
        print("[X] 副本装好了，但该 node 仍加载不了 better-sqlite3（ABI 不匹配）。")
        print("    试试 --node-major 20 / 24，或换一个 --node。")
        sys.exit(1)
    print("[OK] better-sqlite3 ABI 匹配")
    try:
        r = run_clb(node, js, ["sessions", "list", "--format", "json"],
                    resolve_data_dir(None), 120)
        if clb_crashed(r):
            print("[X] 该组合运行 clb 仍会原生崩溃，换个大版本再试。")
            sys.exit(1)
        o = parse_json_envelope(r.stdout)
        if not o or not o.get("ok"):
            print("[!] sessions list 没返回信封，但进程没崩；导入时仍会尝试它。")
        else:
            print("[OK] clb 实跑正常，当前会话数:", len((o.get("data") or {}).get("items") or []))
    except Exception as e:
        print("[!] 验证时出错:", e)

    print("\n[OK] 已就绪:", js)
    print("    之后直接跑 import_chatlab.py 即可，它会自动优先用这份副本。")


if __name__ == "__main__":
    main()
