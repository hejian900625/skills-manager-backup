# -*- coding: utf-8 -*-
"""把导出的 ChatLab echotrace JSON 无界面导入 ChatLab（clb import），不需要 GUI、不需要 .cmd。

用法:
  python import_chatlab.py <echotrace.json> [选项]

选项:
  --data-dir DIR     ChatLab 数据目录（优先级: 本参数 > $CHATLAB_DATA_DIR > ~/.chatlab/data）
  --session-id ID    手工指定导入目标会话（优先级最高）
  --new              强制新建会话，即使已存在同名会话（默认是自动增量合并）
  --dry-run          只分析、不写库（用于预检条数与格式）
  --force            不自动复用已存在会话，交给 clb 自行判断（一般会增量去重）
  --gui              兜底：不走 clb，改为生成 import_to_chatlab.cmd 并拉起桌面版
  --timeout SEC      导入超时秒数（默认 600）

增量规则（默认行为）:
  同一个微信会话重复导入时，脚本会自动找到它**上次落库的那个 ChatLab 会话**并
  带上 --session-id 合并进去，只补新消息，不会建出第二个同名会话。
  查找顺序: --session-id > ~/.chatlab/_wx_import_map.json 记录的 ID（校验仍存在）
            > 同名会话 > 新建。
  因此「每天导出 → 再导入」是天然的增量备份：文件按日期各存一份，数据始终一个会话。

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
  3. 重复导入: 同名/同源会话已存在时自动走增量合并（复用原会话 ID），不会建重复会话；
     要刻意新建第二个会话才需要 --new。
"""
import sys, os, json, shutil, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _clb_common import (  # noqa: E402
    find_clb_js, find_clb_instances, usable_nodes, run_clb, parse_json_envelope,
    resolve_data_dir, ensure_databases_gate, drop_seed, list_sessions,
    clb_crashed, crash_hint, clear_stale_lock, LOCK_NAME,
)
import _state  # noqa: E402

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
    dry_run = force = gui = new_session = False
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
        if a == "--new":
            new_session = True; i += 1; continue
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
    # 会话名可能落在 name / displayName / nickname（WeFlow 风格用后两个），
    # 取不到会让重复检查失效（clb 目录里已存在同名会话却检测不到）。
    name = (sess.get("name") or sess.get("displayName") or sess.get("nickname")
            or (doc.get("chatInfo") or {}).get("name") or "(未命名)")
    is_private = (sess.get("type") == "私聊"
                  or str(sess.get("chatType", "")).lower() == "private"
                  or (bool(sess.get("wxid")) and not str(sess.get("wxid")).endswith("@chatroom")))
    nmsg = len(doc["messages"])
    print("[OK] echotrace 校验通过: %s=%s 消息=%d 条"
          % ("私聊" if is_private else "群", name, nmsg))

    out_dir = out_dir or os.path.dirname(src)

    if gui:
        gui_fallback(src, out_dir)
        return

    # --- 定位 clb（可能有多份 ABI 副本）与每份可用的 node，组成 (node, clb) 候选对
    instances = find_clb_instances()
    if not instances:
        print("[X] 找不到 chatlab-cli 的入口 chatlab.mjs。")
        print("    请先 `npm i -g chatlab-cli`，或用 --gui 走桌面版导入。")
        sys.exit(1)
    print("[i] clb:", instances[0])

    pairs = []
    for js in instances:
        nodes, skipped = usable_nodes(js)
        tag = "" if js == instances[0] else "  [副本 %s]" % os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(js))))
        for s in skipped:
            print("    - 跳过 node:%s %s" % (tag, s))
        for n in nodes:
            pairs.append((n, js))
    if not pairs:
        print("[X] 没有找到能真正使用 better-sqlite3 的 Node（ABI 不匹配）。")
        print("    解决: 用安装 chatlab-cli 时的那个 Node 版本运行，或在该 Node 下执行")
        print("          npm rebuild better-sqlite3")
        print("    兜底: 加 --gui 改为生成 .cmd 走桌面版导入。")
        sys.exit(1)
    data_dir = resolve_data_dir(data_dir)
    print("[i] 数据目录:", data_dir)

    # --- 先探出一个真正能跑通的 (node, clb) 组合
    # 光靠 ABI 探针不够：有的 node 能加载 better-sqlite3，却会让 clb 在解析后原生崩溃。
    # 重复检查若用了崩溃的组合会拿到空列表，误判「没有同名会话」→ 建出重复会话。
    def probe_pair(cand, js):
        try:
            r = run_clb(cand, js, ["sessions", "list", "--format", "json"], data_dir, 120)
        except Exception:
            return None
        if clb_crashed(r):
            return None
        o = parse_json_envelope(r.stdout)
        if not o or not o.get("ok"):
            return None
        return (o.get("data") or {}).get("items") or []

    # sessions list 也要求 databases 非空，先过门槛（占位库稍后统一删）
    seed = ensure_databases_gate(data_dir)
    if seed:
        print("[i] databases 为空，已临时放置占位库过门槛（结束后自动删除）")

    working, probed = None, []
    for cand, js in pairs:
        items = probe_pair(cand, js)
        if items is None:
            probed.append(cand)
            print("[!] 组合不可用（崩溃或无响应），跳过: node=%s clb=%s" % (cand, js))
            clear_stale_lock(data_dir)
            continue
        working = (cand, js, items)
        break
    if not working:
        print("[X] 没有一组 (node, clb) 能正常跑起来。")
        print("    " + crash_hint())
        print("    兜底: 加 --gui 改为生成 .cmd 走桌面版导入。")
        sys.exit(1)
    node, clb_js, existing = working
    if len(pairs) > 1:
        print("[i] 使用 node:", node, "clb:", clb_js)

    # --- 增量检查：状态文件记录的 sessionId > 同名会话 > 新建
    chat_id = str(sess.get("wxid") or (doc.get("chatInfo") or {}).get("id") or "")
    base = os.path.splitext(os.path.basename(src))[0]
    want_names = {name, base}
    # 带日期后缀的文件名（xxx_chatlab_2026-10-22）还原成 xxx 一起比对
    for cand in (name, base):
        if "_chatlab_" in cand:
            want_names.add(cand.rsplit("_chatlab_", 1)[0])
    want_names = {n.strip() for n in want_names if n and n.strip()}
    same = [s for s in existing if (s.get("name") or "").strip() in want_names]

    target, incremental = session_id, False
    if target:
        incremental = any(s.get("id") == target for s in existing)
        print("[i] 指定导入目标会话:", target)
    elif new_session:
        print("[i] --new: 强制新建会话，不复用已有会话")
    elif force:
        print("[i] --force: 不复用会话，交给 clb 自行判断")
    else:
        rec = _state.get_session_record(chat_id) if chat_id else {}
        hit = None
        if rec.get("sessionId"):
            hit = next((s for s in existing if s.get("id") == rec["sessionId"]), None)
            if not hit:
                print("[i] 状态文件记录的会话 %s 已不存在（可能被删），改按会话名匹配"
                      % rec["sessionId"])
        if not hit and same:
            hit = same[0]
        if hit:
            target = hit.get("id")
            incremental = True
            print("[+] 增量导入 → 复用已有会话 %s「%s」(%s 条 / %s 成员)"
                  % (target, hit.get("name"), hit.get("totalMessages"), hit.get("totalMembers")))
            print("    本次只补写新消息，重复内容由 clb 按内容去重；想另建一个独立会话请加 --new。")
        else:
            print("[+] 未找到同一会话 → 新建")

    # --- 导入（占位库已在探测前放过）
    if clear_stale_lock(data_dir):
        print("[i] 已清理上次崩溃残留的导入锁:", LOCK_NAME)
    try:
        cli = ["import", "--json"]
        if dry_run:
            cli.append("--dry-run")
        if target:
            cli += ["--session-id", target]
        cli.append(src)

        env_json = None
        last_raw = ("", "")
        crashed = []
        # 已探明能跑的组排在前面，其余作为兜底
        ordered = [(node, clb_js)] + [p for p in pairs if p != (node, clb_js)]
        for cand, js in ordered:
            tag = " (clb 副本)" if js != instances[0] else ""
            if len(pairs) > 1:
                print("[i] 尝试 node:", cand + tag)
            try:
                r = run_clb(cand, js, cli, data_dir, timeout)
            except subprocess.TimeoutExpired:
                print("[X] 导入超时（%ss）。大群可加 --timeout 900 重试。" % timeout)
                sys.exit(1)
            env_json = parse_json_envelope(r.stdout)
            blob = (r.stdout or "") + (r.stderr or "")
            if env_json and env_json.get("ok"):
                if cand != node or js != clb_js:
                    print("[i] 实际使用 node:", cand, "clb:", js)
                break
            last_raw = (r.stdout or "", r.stderr or "")
            if clb_crashed(r):
                # 原生崩溃：不是 ABI 问题，换下一对（通常是另一份 ABI 副本）
                print("[!] 该 node 上 clb 原生崩溃，换下一个:", cand)
                crashed.append(cand)
                clear_stale_lock(data_dir)
                continue
            # ABI 报错或无信封 → 换下一个再试；其他明确错误则直接终止
            if env_json is None or "NODE_MODULE_VERSION" in blob:
                print("[!] 该 node 不适用于当前 better-sqlite3，换下一个:", cand)
                continue
            err = env_json.get("error") or env_json
            print("[X] 导入失败:", json.dumps(err, ensure_ascii=False)[:800])
            sys.exit(1)

        if not env_json or not env_json.get("ok"):
            if crashed:
                print("[X] 所有可用组合都崩溃了（node: %s）" % ", ".join(crashed))
                print("    " + crash_hint())
            else:
                print("[X] clb 没有返回可解析的 JSON。最后输出:")
                print(last_raw[0][:2000])
                if last_raw[1]:
                    print("STDERR:", last_raw[1][:1000])
            sys.exit(1)

        d = env_json.get("data") or {}
        diag = d.get("diagnostics") or {}
        sid = d.get("sessionId") or target or ("（dry-run 不分配）" if dry_run else "?")
        print()
        print("=" * 58)
        print(("  增量合并完成" if incremental else "  导入成功")
              + ("（dry-run，未写库）" if dry_run else ""))
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

        # 记下「微信会话 → ChatLab 会话 ID」，下次同源导入直接命中，不受改名影响
        if not dry_run and d.get("sessionId"):
            _state.record_session(chat_id, d["sessionId"], name, nmsg, incremental)

        if dry_run:
            print("\n预检通过。去掉 --dry-run 即正式写入。")
        else:
            print("\n桌面版若开着旧会话，刷新/重启 ChatLab 即可看到该会话。")
            if incremental:
                print("下次同一会话再导入会自动并进来（增量），无需手工指定会话 ID。")
            print("后续查询可直接用 ChatLab MCP（list_sessions / search_messages / execute_sql）。")
    finally:
        drop_seed(seed)


if __name__ == "__main__":
    main()
