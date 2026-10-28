# -*- coding: utf-8 -*-
"""wechat-to-chatlab 公用工具：定位 chatlab-cli、挑选 ABI 匹配的 node、读写 clb JSON 信封。

被 import_chatlab.py 与 mcp_launcher.py 共用。只用标准库，任意 Python 3 都能跑。

核心坑（最容易被忽略的一条）:
  chatlab-cli 依赖原生模块 better-sqlite3，它是按某个 Node 版本编译的（本机是 Node 24 /
  ABI 137），而 PATH 里的 node 往往是别的版本（托管 Node 22 / ABI 127）。用错的 node 跑 clb
  会报 NODE_MODULE_VERSION 137 vs 127。
  更坑的是：better-sqlite3 的原生绑定是**懒加载**的，单纯 `require('better-sqlite3')`
  在 Node 22 下**也会成功**（假阳性）。必须真的 `new Database(':memory:')` 并执行一条 SQL
  才能暴露 ABI 不匹配。node_can_load_sqlite() 就是按这个标准探测的。
"""
import os, re, json, glob, shutil, sqlite3, subprocess

DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), ".chatlab", "data")
CACHE_PATH = os.path.join(os.path.expanduser("~"), ".chatlab", ".clb_node_cache.json")


# ---------------------------------------------------------------- clb

def find_clb_js():
    """定位 chatlab-cli 的入口 .mjs（clb 的 npm 全局 shim 背后那个文件）。"""
    env = os.environ.get("CHATLAB_CLB_JS")
    if env and os.path.exists(env):
        return env

    appdata = os.environ.get("APPDATA", "")
    local = os.environ.get("LOCALAPPDATA", "")
    roots = [
        os.path.join(appdata, "npm", "node_modules"),
        os.path.join(local, "npm", "node_modules"),
        r"C:\Program Files\nodejs\node_modules",
        r"D:\nodejs\node_modules",
    ]
    for root in roots:
        pkg = os.path.join(root, "chatlab-cli")
        if not os.path.isdir(pkg):
            continue
        for name in ("chatlab.mjs", "clb.mjs"):
            p = os.path.join(pkg, "bin", name)
            if os.path.exists(p):
                return p
        hits = sorted(glob.glob(os.path.join(pkg, "bin", "*.mjs")))
        if hits:
            return hits[0]

    # 从 PATH 上的 clb.cmd 里抠出绝对路径
    shim = shutil.which("clb")
    if shim:
        try:
            txt = open(shim, encoding="utf-8", errors="ignore").read()
            m = re.search(r"([A-Za-z]:[^\s\"']*\.mjs)", txt)
            if m and os.path.exists(m.group(1)):
                return m.group(1)
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- node

def node_candidates():
    """按优先级列出可能的 node.exe（去重、只保留真实存在的）。"""
    seen, out = set(), []

    def add(p):
        if not p:
            return
        p = os.path.normpath(p)
        key = p.lower() if os.name == "nt" else p  # Windows: node.exe / node.EXE 是同一个
        if key in seen or not os.path.isfile(p):
            return
        seen.add(key)
        out.append(p)

    add(os.environ.get("CHATLAB_NODE"))
    add(shutil.which("node.exe"))
    add(shutil.which("node"))
    add(r"D:\nodejs\node.exe")
    add(r"C:\Program Files\nodejs\node.exe")
    add(os.path.join(os.environ.get("APPDATA", ""), "npm", "node.exe"))
    for d in sorted(glob.glob(os.path.expanduser(
            "~/.workbuddy/binaries/node/versions/*/node.exe")), reverse=True):
        add(d)
    return out


def node_can_load_sqlite(node, clb_js):
    """探针：这个 node 能否真正用起来 better-sqlite3（ABI 是否匹配）。

    必须实际开内存库 + 执行 SQL，只 require 会假阳性（见模块文档）。
    """
    js = (
        "try{const p=require.resolve('better-sqlite3',{paths:[process.argv[1]]});"
        "const D=require(p);const db=new D(':memory:');"
        "db.prepare('select 1 as x').get();db.close();console.log('OK')}"
        "catch(e){console.log('FAIL '+String(e.message).split('\\n')[0])}"
    )
    try:
        r = subprocess.run([node, "-e", js, os.path.dirname(clb_js)],
                           capture_output=True, text=True, timeout=40,
                           encoding="utf-8", errors="replace")
        return "OK" in (r.stdout or "")
    except Exception:
        return False


def _node_version(node):
    try:
        return subprocess.run([node, "-v"], capture_output=True, text=True,
                              timeout=15).stdout.strip() or "?"
    except Exception:
        return "?"


def _cache_key(clb_js):
    try:
        st = os.stat(clb_js)
        return "%s|%d|%d" % (os.path.abspath(clb_js).lower(), st.st_size, int(st.st_mtime))
    except OSError:
        return None


def _read_cache(key):
    if not key:
        return None
    try:
        d = json.load(open(CACHE_PATH, encoding="utf-8"))
        if d.get("key") == key:
            return d.get("node")
    except Exception:
        pass
    return None


def _write_cache(key, node):
    if not key:
        return
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        json.dump({"key": key, "node": node}, open(CACHE_PATH, "w", encoding="utf-8"))
    except Exception:
        pass


def usable_nodes(clb_js, allow_cache=True):
    """所有 ABI 匹配的 node（缓存命中的排最前）；同时给出被跳过的清单。

    allow_cache 只控制「读」缓存（快路径直接信缓存再验证）；**不管读不读，命中后都会写缓存**。
    """
    good, skipped = [], []
    key = _cache_key(clb_js)
    cached = _read_cache(key) if allow_cache else None
    cands = node_candidates()
    if cached and os.path.isfile(cached):
        if node_can_load_sqlite(cached, clb_js):
            good.append(cached)
        cands = [n for n in cands if os.path.normcase(n) != os.path.normcase(cached)]
    for n in cands:
        if node_can_load_sqlite(n, clb_js):
            good.append(n)
        else:
            skipped.append("%s (%s, better-sqlite3 ABI 不匹配)" % (n, _node_version(n)))
    if good:
        _write_cache(key, good[0])
    return good, skipped


def pick_node(clb_js, allow_cache=True):
    """只要一个可用 node 时的快路径：缓存命中就只探一个，否则逐个探。

    返回 (node 或 None, 被跳过的清单)。
    """
    key = _cache_key(clb_js) if allow_cache else None
    cached = _read_cache(key)
    if cached and os.path.isfile(cached) and node_can_load_sqlite(cached, clb_js):
        return cached, []
    good, skipped = usable_nodes(clb_js, allow_cache=False)
    return (good[0] if good else None), skipped


# ---------------------------------------------------------------- clb 调用

def run_clb(node, clb_js, args, data_dir, timeout):
    env = os.environ.copy()
    env["CHATLAB_DATA_DIR"] = data_dir
    env["NO_COLOR"] = "1"
    env.setdefault("FORCE_COLOR", "0")
    return subprocess.run([node, clb_js] + args, capture_output=True, text=True,
                          env=env, timeout=timeout, encoding="utf-8", errors="replace")


def parse_json_envelope(stdout):
    """clb 会把 [Parser V2] 之类的日志混进 stdout，逐行找最后一个合法 JSON 信封。"""
    found = None
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if isinstance(o, dict) and "ok" in o:
            found = o
    return found


# ---------------------------------------------------------------- 数据目录

def resolve_data_dir(cli_dir=None):
    d = cli_dir or os.environ.get("CHATLAB_DATA_DIR") or DEFAULT_DATA_DIR
    return os.path.abspath(os.path.expanduser(d))


def ensure_databases_gate(data_dir):
    """databases/ 为空时 clb 会直接拒绝；临时放个占位库过门槛。

    返回占位库路径（调用方负责删除）；已有真实库则返回 None。
    """
    d = os.path.join(data_dir, "databases")
    os.makedirs(d, exist_ok=True)
    if any(f.endswith(".db") for f in os.listdir(d)):
        return None
    seed = os.path.join(d, "_clb_gate_seed.db")
    c = sqlite3.connect(seed)
    try:
        c.execute("create table if not exists t(x)")
        c.commit()
    finally:
        c.close()
    return seed


def drop_seed(seed):
    if not seed:
        return
    for suf in ("", "-wal", "-shm", "-journal"):
        try:
            os.remove(seed + suf)
        except OSError:
            pass


def list_sessions(node, clb_js, data_dir):
    """clb sessions list（注意：不吃 --json，要用 --format json）。"""
    try:
        r = run_clb(node, clb_js, ["sessions", "list", "--format", "json"],
                    data_dir, timeout=90)
    except Exception:
        return []
    o = parse_json_envelope(r.stdout)
    if not o:
        return []
    return (o.get("data") or {}).get("items") or []
