# -*- coding: utf-8 -*-
"""把 chatlab MCP 条目写进 ~/.workbuddy/mcp.json —— 指向 mcp_launcher.py 而不是写死的 node。

写死 node 路径的配置在「升级 Node / npm rebuild」后会失效（better-sqlite3 ABI 变更）。
本脚本改成：

    "chatlab": {
      "type": "stdio",
      "command": "<python.exe>",
      "args": ["<...>/scripts/mcp_launcher.py"],
      "env": { "CHATLAB_DATA_DIR": "C:\\Users\\Lenovo\\.chatlab\\data" }
    }

python 只跑启动器（纯标准库），真正的 node 由启动器在每次启动时探测。

用法:
  python install_mcp.py [--data-dir DIR] [--dry-run] [--no-verify]

  --data-dir DIR   指定 CHATLAB_DATA_DIR（默认沿用现有配置，没有就用 ~/.chatlab/data）
  --dry-run        只打印将要写入的条目，不改文件
  --no-verify      写完不做 MCP 握手自检
"""
import sys, os, io, json, shutil, datetime, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _clb_common import resolve_data_dir, find_clb_js  # noqa: E402

MCP_JSON = os.path.join(os.path.expanduser("~"), ".workbuddy", "mcp.json")
LAUNCHER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp_launcher.py")


def build_entry(python_exe, data_dir):
    return {
        "type": "stdio",
        "command": python_exe,
        "args": [LAUNCHER],
        "env": {"CHATLAB_DATA_DIR": data_dir},
    }


def verify(timeout=40):
    """用真实 MCP 握手验证启动器可用：initialize + tools/list。"""
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "install_mcp", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    payload = "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in msgs)
    try:
        r = subprocess.run([sys.executable, LAUNCHER], input=payload.encode("utf-8"),
                           capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        return False, "握手超时", out, (e.stderr or b"").decode("utf-8", "replace")

    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    server, ntools = None, None
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("id") == 1:
            server = (o.get("result") or {}).get("serverInfo")
        if o.get("id") == 2:
            ntools = len((o.get("result") or {}).get("tools") or [])
    if server and ntools is not None:
        return True, "serverInfo=%s, tools=%d" % (json.dumps(server, ensure_ascii=False), ntools), out, err
    return False, "没有拿到 initialize/tools/list 响应", out, err


def main():
    argv = sys.argv[1:]
    data_dir_cli = None
    dry_run = no_verify = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--dry-run":
            dry_run = True; i += 1; continue
        if a == "--no-verify":
            no_verify = True; i += 1; continue
        if a == "--data-dir" and i + 1 < len(argv):
            data_dir_cli = argv[i + 1]; i += 2; continue
        if a.startswith("--data-dir="):
            data_dir_cli = a.split("=", 1)[1]; i += 1; continue
        print("[X] 未知参数:", a); sys.exit(2)

    if not os.path.exists(LAUNCHER):
        print("[X] 缺少启动器:", LAUNCHER); sys.exit(1)

    # 读现有配置（保留其它 server）
    cfg = {}
    if os.path.exists(MCP_JSON):
        try:
            cfg = json.load(open(MCP_JSON, encoding="utf-8"))
        except Exception as e:
            print("[X] 现有 mcp.json 解析失败，已中止以免覆盖:", e); sys.exit(1)
    servers = cfg.setdefault("mcpServers", {})

    old = servers.get("chatlab") or {}
    old_env = (old.get("env") or {}).get("CHATLAB_DATA_DIR")
    data_dir = resolve_data_dir(data_dir_cli or old_env)
    entry = build_entry(sys.executable, data_dir)

    print("[i] mcp.json   :", MCP_JSON)
    print("[i] python     :", sys.executable)
    print("[i] launcher   :", LAUNCHER)
    print("[i] data dir   :", data_dir)
    clb = find_clb_js()
    print("[i] chatlab-cli:", clb or "未找到（启动时会再试）")
    print()
    print("将写入 chatlab 条目:")
    print(json.dumps({"chatlab": entry}, ensure_ascii=False, indent=2))

    if dry_run:
        print("\n--dry-run：未改动文件。")
        return

    # 备份 + 写回
    if os.path.exists(MCP_JSON):
        bak = MCP_JSON + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.copy2(MCP_JSON, bak)
        print("\n[i] 已备份原配置:", bak)

    servers["chatlab"] = entry
    tmp = MCP_JSON + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, MCP_JSON)
    print("[OK] 已写入", MCP_JSON, "（现有 server:", ", ".join(servers.keys()), "）")

    if no_verify:
        return
    print("\n[i] 用启动器做 MCP 握手自检 ...")
    ok, detail, out, err = verify()
    if ok:
        print("[OK]", detail)
    else:
        print("[X]", detail)
        if out:
            print("  stdout:", out[:600])
        if err:
            print("  stderr:", err[-800:])
        sys.exit(1)

    print("\n最后一步（必须手动）: 连接器管理 → 右上角「自定义连接器」→ chatlab → Trust")


if __name__ == "__main__":
    main()
