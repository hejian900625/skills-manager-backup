# -*- coding: utf-8 -*-
"""把导出的 ChatLab echotrace JSON 无界面导入 ChatLab（clb import），不需要 GUI、不需要 .cmd。

用法:
  python import_chatlab.py <echotrace.json> [选项]

选项:
  --data-dir DIR     ChatLab 数据目录（优先级: 本参数 > $CHATLAB_DATA_DIR > ~/.chatlab/data）
  --session-id ID    导入到指定已存在会话（按内容去重合并，不会重复建会话）
  --dry-run          只分析、不写库（用于预检条数与格式）
  --force            同名会话已存在时也继续交给 clb（实测 clb 会按内容增量去重，
                     一般不会新建重复会话，只是白跑一趟）
  --gui              兜底：不走 clb，改为生成 import_to_chatlab.cmd 并拉起桌面版
  --timeout SEC      导入超时秒数（默认 600）

为什么要走 clb 而不是 GUI:
  ChatLab 桌面版没有无头模式，沙箱/后台环境拉不起窗口；而 `clb import` 是官方 CLI，
  原生支持 echotrace 格式，可直接写入数据目录，全程无需开窗。

本脚本会自动处理三个已知坑:
  1. Node ABI 不匹配: better-sqlite3 按某个 Node 版本编译（如 Node 24 / ABI 137），
     而 PATH 里的 node 可能是别的版本（如 Node 22 / ABI 127）。脚本逐个探测
     "能真正打开 better-sqlite3 内存库" 的 node（见 _clb_common.node_can_load_sqlite），
     并在导入报 ABI 错时自动换下一个 node 重试。
  2. databases 门槛: `clb import` 在 `<data>/databases` 为空时一律拒绝（连 --dry-run 都不给跑），
     脚本临时放一个占位库过门槛，结束后自动删除（只删自己建的那个）。
  3. 重复导入: 同名会话已存在时默认跳过。
     注意 ChatLab 落库的会话名取的是「导入文件名」而不是 JSON 里的 session.name，脚本两个都比对。
"""
import sys, os, json, shutil, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _clb_common import (  # noqa: E402
    find_clb_js, usable_nodes, run_clb, parse_json_envelope,
    resolve_data_dir, ensure_databases_gate, drop_seed, list_sessions,
)

CHATLAB_EXE_FALLBACK = [
    r"D:\Program Files\ChatLab\ChatLab.exe",
    r"C:\Program Files\ChatLab\ChatLab.exe",
]


# ---------------------------------------------------------------- GUI 兜底

def gui_fallback(src, out_dir):
    """生成纯 ASCII 的 .cmd 启动器并尝试拉起桌面版（旧路径，仅 --gui 时用）。"""
    exe = None
    for c in CHATLAB_EXE_FALLBACK:
        if os.path.exists(c):
            exe = c
            break
    if not exe:
        exe = shutil.which("ChatLab.exe")

    os.makedirs(out_dir, exist_ok=True)
    copy = os.path.join(out_dir, "chatlab_import.json")
    shutil.copy2(src, copy)
    print("已复制为 ASCII 名:", copy)

    cmd = os.path.join(out_dir, "import_to_chatlab.cmd")
    lines = [
        "@echo off",
        "setlocal",
        'set "CHATLAB=' + ((exe or r"D:\Program Files\ChatLab\ChatLab.exe").replace("/", "\\")) + '"',
        'if not exist "%CHATLAB%" (',
        "  echo [ERROR] ChatLab.exe not found. Edit CHATLAB path in this file.",
        "  pause",
        "  exit /b 1",
        ")",
        'set "JSON=%~dp0chatlab_import.json"',
        'if not exist "%JSON%" ( echo [ERROR] chatlab_import.json missing & pause & exit /b 1 )',
        'start "" "%CHATLAB%" "%JSON%"',
        "exit /b 0",
        "",
    ]
    with open(cmd, "w", encoding="ascii", newline="\r\n") as f:
        f.write("\r\n".join(lines))
    print("已生成启动器:", cmd)

    if exe:
        try:
            subprocess.Popen([exe, copy])
            print("[i] 已尝试拉起 ChatLab。若窗口没出现，直接双击上面的 .cmd。")
        except Exception as e:
            print("[!] 拉起失败:", e, "——请双击", cmd)
    else:
        print("[!] 未找到 ChatLab.exe，请先编辑", cmd, "里的 CHATLAB 路径。")


# ---------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    src = out_dir = data_dir = session_id = None
    dry_run = force = gui = False
    timeout = 600
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            print(__doc__)
            return
        if a == "--dry-run":
            dry_run = True; i += 1; continue
        if a == "--force":
            force = True; i += 1; continue
        if a == "--gui":
            gui = True; i += 1; continue
        if a.startswith("--") and "=" in a:
            k, v = a.split("=", 1)
            if k == "--data-dir":
                data_dir = v
            elif k == "--session-id":
                session_id = v
            elif k == "--out-dir":
                out_dir = v
            elif k == "--timeout":
                timeout = int(v)
            i += 1; continue
        if a in ("--data-dir", "--session-id", "--out-dir", "--timeout"):
            if i + 1 >= len(args):
                print("[X]", a, "缺少参数值"); sys.exit(1)
            v = args[i + 1]
            if a == "--data-dir":
                data_dir = v
            elif a == "--session-id":
                session_id = v
            elif a == "--out-dir":
                out_dir = v
            else:
                timeout = int(v)
            i += 2; continue
        if src is None:
            src = a
        i += 1

    if not src:
        print(__doc__)
        sys.exit(1)
    if not os.path.exists(src):
        print("[X] 找不到文件:", src); sys.exit(1)
    src = os.path.abspath(src)

    # --- 校验 echotrace 结构
    try:
        doc = json.load(open(src, encoding="utf-8"))
    except Exception as e:
        print("[X] JSON 解析失败:", e); sys.exit(1)
    if not (isinstance(doc, dict) and "session" in doc and "messages" in doc):
        print("[X] 不是 ChatLab echotrace JSON（缺少 session/messages）"); sys.exit(1)
    sess = doc.get("session") or {}
    name = sess.get("name") or "(未命名)"
    nmsg = len(doc["messages"])
    print("[OK] echotrace 校验通过: 群=%s 消息=%d 条" % (name, nmsg))

    out_dir = out_dir or os.path.dirname(src)

    if gui:
        gui_fallback(src, out_dir)
        return

    # --- 定位 clb 与可用 node
    clb_js = find_clb_js()
    if not clb_js:
        print("[X] 找不到 chatlab-cli 的入口 chatlab.mjs。")
        print("    请先 `npm i -g chatlab-cli`，或用 --gui 走桌面版导入。")
        sys.exit(1)
    print("[i] clb:", clb_js)

    nodes, skipped = usable_nodes(clb_js)
    for s in skipped:
        print("    - 跳过 node:", s)
    if not nodes:
        print("[X] 没有找到能真正使用 better-sqlite3 的 Node（ABI 不匹配）。")
        print("    解决: 用安装 chatlab-cli 时的那个 Node 版本运行，或在该 Node 下执行")
        print("          npm rebuild better-sqlite3")
        print("    兜底: 加 --gui 改为生成 .cmd 走桌面版导入。")
        sys.exit(1)
    node = nodes[0]
    print("[i] node:", node)

    data_dir = resolve_data_dir(data_dir)
    print("[i] 数据目录:", data_dir)

    # --- 重复导入检查（会话名可能来自 JSON 或导入文件名，两个都比）
    want_names = {name, os.path.splitext(os.path.basename(src))[0]}
    want_names = {n.strip() for n in want_names if n and n.strip()}
    existing = []
    if os.path.isdir(os.path.join(data_dir, "databases")):
        existing = list_sessions(node, clb_js, data_dir)
    same = [s for s in existing if (s.get("name") or "").strip() in want_names]
    if session_id:
        print("[i] 指定导入目标会话:", session_id)
    elif same and not force:
        for s in same:
            print("[!] 已存在同名会话: %s  (%s 条 / %s 成员)"
                  % (s.get("id"), s.get("totalMessages"), s.get("totalMembers")))
        print("    默认跳过，避免白跑。要给它补新旧消息（增量去重合并），加 --session-id <上面的 id>；")
        print("    只是想让 clb 再比对一次，加 --force。")
        return

    # --- 过 databases 门槛 + 导入
    seed = ensure_databases_gate(data_dir)
    if seed:
        print("[i] databases 为空，已临时放置占位库过门槛（结束后自动删除）")
    try:
        cli = ["import", "--json"]
        if dry_run:
            cli.append("--dry-run")
        if session_id:
            cli += ["--session-id", session_id]
        cli.append(src)

        env_json = None
        last_raw = ("", "")
        for cand in nodes:
            try:
                r = run_clb(cand, clb_js, cli, data_dir, timeout)
            except subprocess.TimeoutExpired:
                print("[X] 导入超时（%ss）。大群可加 --timeout 900 重试。" % timeout)
                sys.exit(1)
            env_json = parse_json_envelope(r.stdout)
            blob = (r.stdout or "") + (r.stderr or "")
            if env_json and env_json.get("ok"):
                if cand != node:
                    print("[i] 改用 node:", cand)
                break
            last_raw = (r.stdout or "", r.stderr or "")
            # ABI 报错或无信封 → 换下一个 node 再试；其他明确错误则直接终止
            if env_json is None or "NODE_MODULE_VERSION" in blob:
                print("[!] 该 node 不适用于当前 better-sqlite3，换下一个:", cand)
                continue
            err = env_json.get("error") or env_json
            print("[X] 导入失败:", json.dumps(err, ensure_ascii=False)[:800])
            sys.exit(1)

        if not env_json:
            print("[X] clb 没有返回可解析的 JSON。最后输出:")
            print(last_raw[0][:2000])
            if last_raw[1]:
                print("STDERR:", last_raw[1][:1000])
            sys.exit(1)
        if not env_json.get("ok"):
            err = env_json.get("error") or env_json
            print("[X] 导入失败:", json.dumps(err, ensure_ascii=False)[:800])
            sys.exit(1)

        d = env_json.get("data") or {}
        diag = d.get("diagnostics") or {}
        sid = d.get("sessionId") or session_id or ("（dry-run 不分配）" if dry_run else "?")
        print()
        print("=" * 58)
        print("  导入成功" + ("（dry-run，未写库）" if dry_run else ""))
        print("=" * 58)
        print("  会话 ID   :", sid)
        print("  会话名    :", name)
        print("  写入消息  :", d.get("newMessageCount", diag.get("messagesWritten", "?")))
        print("  重复跳过  :", d.get("duplicateCount", diag.get("duplicateCount", "?")))
        if diag.get("messagesSkipped"):
            print("  无法解析  :", diag.get("messagesSkipped"))
        print("  识别格式  :", diag.get("detectedFormat") or ("（dry-run 不返回）" if dry_run else "?"))
        print("  导入模式  :", d.get("importMode") or "?", "/", d.get("createReason") or "")
        if not dry_run and d.get("sessionId"):
            db = os.path.join(data_dir, "databases", d["sessionId"] + ".db")
            if os.path.exists(db):
                print("  数据库    : %s  (%.0f KB)" % (db, os.path.getsize(db) / 1024.0))
        print("=" * 58)

        if dry_run:
            print("\n预检通过。去掉 --dry-run 即正式写入。")
        else:
            print("\n桌面版若开着旧会话，刷新/重启 ChatLab 即可看到该会话。")
            print("后续查询可直接用 ChatLab MCP（list_sessions / search_messages / execute_sql）。")
    finally:
        drop_seed(seed)


if __name__ == "__main__":
    main()
