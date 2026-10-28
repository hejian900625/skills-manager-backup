# -*- coding: utf-8 -*-
"""ChatLab MCP 启动器：启动时动态挑选 ABI 匹配的 node，再把 stdio 透传给 `clb mcp`。

为什么需要这层:
  在 mcp.json 里把 node 路径写死很脆——一旦升级 Node、或用别的 Node 执行过
  `npm rebuild better-sqlite3`，ABI 就变了，MCP 直接起不来（报 NODE_MODULE_VERSION 137 vs 127）。
  这个启动器每次被 MCP 客户端拉起时都现场探测"哪个 node 真的能用 better-sqlite3"
  （结果会缓存到 ~/.chatlab/.clb_node_cache.json），挑中后把 stdin/stdout/stderr
  直接交给 `node <chatlab.mjs> mcp`，自己只负责等待。

用法（由 ~/.workbuddy/mcp.json 调用，一般不用手跑）:
  python mcp_launcher.py [--data-dir DIR]

重要: 本进程运行在 MCP stdio 协议下，**绝不能往 stdout 打印任何东西**，
      否则会污染 JSON-RPC 流导致客户端解析失败。诊断信息一律写 stderr。
"""
import sys, os, json, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _clb_common import (
    find_clb_js, find_clb_instances, usable_nodes, pick_node, resolve_data_dir,
    node_candidates, run_clb, clb_crashed, parse_json_envelope,
)

PAIR_CACHE = os.path.join(os.path.expanduser("~"), ".chatlab", ".clb_pair_cache.json")


def log(msg):
    try:
        sys.stderr.write("[chatlab-mcp] %s\n" % msg)
        sys.stderr.flush()
    except Exception:
        pass


def _pair_key(node, js):
    try:
        st = os.stat(js)
        return "%s|%s|%d" % (os.path.normcase(node), os.path.normcase(js), int(st.st_mtime))
    except OSError:
        return None


def _read_pair_cache(key):
    if not key:
        return None
    try:
        d = json.load(open(PAIR_CACHE, encoding="utf-8"))
        if d.get("key") == key and os.path.isfile(d.get("js", "")):
            return d.get("node"), d.get("js")
    except Exception:
        pass
    return None


def _write_pair_cache(key, node, js):
    if not key:
        return
    try:
        os.makedirs(os.path.dirname(PAIR_CACHE), exist_ok=True)
        json.dump({"key": key, "node": node, "js": js},
                  open(PAIR_CACHE, "w", encoding="utf-8"))
    except Exception:
        pass


def pick_pair(data_dir):
    """挑一组真能跑起来的 (node, clb)。

    仅靠 ABI 探测不够：某些 node 能加载 better-sqlite3，却让 clb 在启动后原生崩溃。
    用 `sessions list` 做一次轻量探活，命中后缓存，后续启动免探测。
    """
    key = None
    firsts = []
    for js in find_clb_instances():
        nodes, _ = usable_nodes(js)
        for n in nodes:
            firsts.append((n, js))
            if key is None:
                key = _pair_key(n, js)
    if not firsts:
        return None, None

    cached = _read_pair_cache(key)
    if cached:
        return cached

    for n, js in firsts:
        try:
            r = run_clb(n, js, ["sessions", "list", "--format", "json"], data_dir, 120)
        except Exception:
            continue
        if clb_crashed(r):
            log("跳过（clb 原生崩溃）: node=%s" % n)
            continue
        o = parse_json_envelope(r.stdout)
        if o and o.get("ok"):
            _write_pair_cache(_pair_key(n, js), n, js)
            return n, js

    log("探活都没通过，退回首个 ABI 匹配组合")
    return firsts[0]


def main():
    argv = sys.argv[1:]
    data_dir = None
    if "--data-dir" in argv:
        k = argv.index("--data-dir")
        if k + 1 < len(argv):
            data_dir = argv[k + 1]

    if not find_clb_js() and not find_clb_instances():
        log("找不到 chatlab-cli 入口（chatlab.mjs）。请先 npm i -g chatlab-cli，"
            "或设置 CHATLAB_CLB_JS 指向该文件。")
        return 127

    data_dir_abs = resolve_data_dir(data_dir)
    node, clb_js = pick_pair(data_dir_abs)
    if not node or not clb_js:
        log("没有找到能真正使用 better-sqlite3 的 Node（ABI 不匹配）。")
        log("可在 candidates 里手工指定 CHATLAB_NODE=<node.exe 路径>；"
            "已探测候选: " + ", ".join(node_candidates()))
        return 127

    env = os.environ.copy()
    env["CHATLAB_DATA_DIR"] = data_dir_abs
    env["NO_COLOR"] = "1"
    env["FORCE_COLOR"] = "0"

    log("node=%s" % node)
    log("clb=%s" % clb_js)
    log("data=%s" % env["CHATLAB_DATA_DIR"])

    try:
        proc = subprocess.Popen(
            [node, clb_js, "mcp"],
            stdin=sys.stdin.buffer,
            stdout=sys.stdout.buffer,
            stderr=sys.stderr.buffer,
            env=env,
        )
    except Exception as e:
        log("拉起 clb mcp 失败: %s" % e)
        return 127

    try:
        rc = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        rc = 130
    log("clb mcp 退出，code=%s" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
