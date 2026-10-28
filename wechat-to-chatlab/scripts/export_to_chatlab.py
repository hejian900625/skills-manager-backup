# -*- coding: utf-8 -*-
"""
把本地微信(4.x)某个**群聊或私聊**的文字消息导出为 ChatLab 的 echotrace JSON，可直接导入 ChatLab。
复用 wechat-cli skill 的解密原语(wcdb_key_tool_windows)与 zstandard。

用法:
  python export_to_chatlab.py "<群名/联系人备注关键词 或 完整@chatroom ID>" [输出路径]

第二参数可以是:
  * 目录          → 写 <目录>/<会话名>_chatlab_<YYYY-MM-DD>.json
  * 具体 .json    → 完全按你给的名字写（老用法，向后兼容）
  * 省略          → 当前目录下 <会话名>_chatlab_<YYYY-MM-DD>.json

例:
  python export_to_chatlab.py "夸夸"  ./exports
  python export_to_chatlab.py "李嘉杰-电网"                       # 私聊联系人
  python export_to_chatlab.py "夸夸" 大佬夸夸群_ChatLab.json       # 显式文件名
"""
import sys, os, json, hashlib, sqlite3, tempfile, datetime, collections, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _state  # noqa: E402

# ---------- 定位 wechat-cli skill 的 scripts（解密原语 + zstandard）----------
WXCLI_CANDIDATES = [
    r"C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts",
    r"C:/Users/Lenovo/.skills-manager/skills/wechat-cli/scripts",
]
WXCLI_SCRIPTS = next((p for p in WXCLI_CANDIDATES if os.path.isdir(p)), None)
if not WXCLI_SCRIPTS:
    print("[X] 找不到 wechat-cli skill 的 scripts 目录，请先安装/启用 wechat-cli 技能")
    sys.exit(1)
sys.path.insert(0, WXCLI_SCRIPTS)
import wcdb_key_tool_windows as W
import zstandard as zstd

ZC = zstd.ZstdDecompressor()
def zdecomp(b):
    try:
        return ZC.decompress(b)
    except Exception:
        try:
            return ZC.decompressobj().decompress(b)
        except Exception:
            return b

KEYS_PATH = r"C:/Users/Lenovo/.wechat-cli/all_keys.json"
keys = json.load(open(KEYS_PATH, encoding="utf-8"))
DBDIR = keys["_db_dir"]
# 本账号 wxid：数据目录形如 <wxid>_<rand>，取前缀
WX_ROOT = os.path.dirname(DBDIR)
SELF_WXID = os.path.basename(WX_ROOT).split("_")[0]

GROUP_ARG = sys.argv[1] if len(sys.argv) > 1 else None
if not GROUP_ARG:
    print('用法: python export_to_chatlab.py "<群名关键词 或 @chatroom>" [输出目录或json]')
    sys.exit(1)
OUT_ARG = sys.argv[2] if len(sys.argv) > 2 else None   # 目录或文件名，解析完会话名后再定


def resolve_out(arg, chat_name):
    """输出路径：目录 → 目录/带日期文件名；.json → 原样；省略 → 当前目录带日期。"""
    name = _state.default_export_name(chat_name)
    if not arg:
        return name
    if os.path.isdir(arg) or arg.endswith(("/", "\\")):
        os.makedirs(arg, exist_ok=True)
        return os.path.join(arg, name)
    if arg.lower().endswith(".json"):
        parent = os.path.dirname(arg)
        if parent:
            os.makedirs(parent, exist_ok=True)
        return arg
    # 既不是目录也不是 .json：当成目录建出来
    os.makedirs(arg, exist_ok=True)
    return os.path.join(arg, name)

# ---------- 1. 定位群 ----------
def decrypt(path, rel):
    tmp = tempfile.mkdtemp(prefix="wxc_"); out = os.path.join(tmp, "p.db")
    if rel not in keys:
        return None
    if not W._decrypt_database(path, out, bytes.fromhex(keys[rel]["enc_key"])):
        return None
    return out

ct = decrypt(os.path.join(DBDIR, "contact", "contact.db"), "contact\\contact.db")
cc = sqlite3.connect(ct); cc.row_factory = sqlite3.Row

group_id = None
group_name = None
chat_kind = "group"      # group | private
session_nick = None      # 私聊对方的原始昵称（session.nickname）
if "@chatroom" in GROUP_ARG:
    group_id = GROUP_ARG
    r = cc.execute("SELECT nick_name, remark FROM contact WHERE username=?", (group_id,)).fetchone()
    group_name = (r["remark"] or r["nick_name"] if r else None) or group_id
    session_nick = (r["nick_name"] if r else None) or group_name
else:
    like = f"%{GROUP_ARG}%"
    rows = cc.execute(
        "SELECT username, nick_name, remark FROM contact "
        "WHERE username LIKE '%@chatroom%' AND (nick_name LIKE ? OR remark LIKE ?)",
        (like, like)).fetchall()
    if rows:
        print(f"匹配到 {len(rows)} 个群:")
        for r in rows:
            print(f"  - {r['remark'] or r['nick_name']}  <{r['username']}>")
        exact = [r for r in rows if (r["remark"] or r["nick_name"]) == GROUP_ARG]
        r0 = exact[0] if exact else rows[0]
        group_id = r0["username"]
        group_name = r0["remark"] or r0["nick_name"] or group_id
        session_nick = r0["nick_name"] or group_name
    else:
        # 不是群 → 按私聊联系人找（备注 > 昵称 > 微信号）
        rows = cc.execute(
            "SELECT username, nick_name, remark, alias FROM contact "
            "WHERE username NOT LIKE '%@chatroom%' "
            "AND (remark LIKE ? OR nick_name LIKE ? OR alias LIKE ?)",
            (like, like, like)).fetchall()
        print(f"匹配到 {len(rows)} 个联系人（私聊）:")
        for r in rows:
            print(f"  - {r['remark'] or r['nick_name']}  <{r['username']}>  alias={r['alias']}")
        if not rows:
            print("[X] 未找到群或联系人，退出"); sys.exit(1)
        exact = [r for r in rows if (r["remark"] or r["nick_name"]) == GROUP_ARG or r["alias"] == GROUP_ARG]
        r0 = exact[0] if exact else rows[0]
        group_id = r0["username"]
        group_name = r0["remark"] or r0["nick_name"] or group_id
        session_nick = r0["nick_name"] or group_name
        chat_kind = "private"

print(f"\n{'群' if chat_kind == 'group' else '联系人'}: {group_name}\nID: {group_id}")
OUT = resolve_out(OUT_ARG, group_name)
print(f"导出日期: {_state.today()}  →  输出: {OUT}")
TBL = "Msg_" + hashlib.md5(group_id.encode()).hexdigest()

# 群主（仅群聊有）
owner_id = None
if chat_kind == "group":
    try:
        rr = cc.execute("SELECT owner FROM chat_room WHERE username=?", (group_id,)).fetchone()
        if rr and rr["owner"]:
            owner_id = rr["owner"]
    except Exception as e:
        print("  (chat_room 无群主记录:", e, ")")

# 联系人名表
names = {}
for r in cc.execute("SELECT username, remark, nick_name, alias FROM contact"):
    names[r["username"]] = r["remark"] or r["nick_name"] or r["alias"] or r["username"]
self_user = None
for u in names:
    if u.startswith(SELF_WXID):
        self_user = u; break
if self_user:
    names[self_user] = "我"
cc.close()

# ---------- 2. 遍历 message_N.db 取消息 ----------
all_rows = []
n2i_all = {}  # 全局 Name2Id 并集(跨所有 message 库, 解决某库缺成员映射的问题)
for fn in sorted(os.listdir(os.path.join(DBDIR, "message"))):
    if not (fn.startswith("message_") and fn.endswith(".db") and fn.count("_") == 1):
        continue
    rel = "message\\" + fn
    if rel not in keys:
        continue
    src = os.path.join(DBDIR, "message", fn)
    out = decrypt(src, rel)
    if not out:
        continue
    con = sqlite3.connect(out); con.row_factory = sqlite3.Row
    try:
        for r in con.execute("SELECT rowid, user_name FROM Name2Id"):
            n2i_all.setdefault(r[0], r[1])
    except Exception:
        pass
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (TBL,)).fetchone():
        con.close(); continue
    rows = [dict(r) for r in con.execute(f"SELECT * FROM {TBL}")]
    n2i = {r[0]: r[1] for r in con.execute("SELECT rowid, user_name FROM Name2Id")}
    for r in rows: r["_n2i"] = n2i
    print(f"[+] {fn}: {len(rows)} 条")
    all_rows.extend(rows); con.close()

if not all_rows:
    print("[X] 该群无消息"); sys.exit(0)

seen = set(); uniq = []
for r in all_rows:
    sid = r.get("server_id") or 0
    if sid:
        k = (sid, r.get("local_id"))
        if k in seen: continue
        seen.add(k)
    uniq.append(r)
uniq = [r for r in uniq if r.get("create_time")]
uniq.sort(key=lambda r: r["create_time"])
print(f"合并 {len(all_rows)} → 去重后 {len(uniq)} 条")

# ---------- 3. 渲染为 ChatLab echotrace 消息 ----------
APP = {"5":"链接","6":"文件","19":"聊天记录","33":"小程序","36":"小程序·点评",
       "44":"文章","51":"视频号","57":"引用","62":"视频号","87":"公告","2000":"转账"}
def app_card(c):
    ti = re.search(r"<title>(.*?)</title>", c, re.S)
    de = re.search(r"<des>(.*?)</des>", c, re.S)
    ty = re.search(r"<type>(\d+)</type>", c)
    url = re.search(r"<url>(.*?)</url>", c, re.S)
    fe = re.search(r"<fileext>(.*?)</fileext>", c, re.S)
    kind = APP.get(ty.group(1) if ty else "")
    if not kind:
        if fe: kind = "文件·" + fe.group(1)
        elif "<finderFeed>" in c: kind = "视频号"
        else: kind = "卡片"
    s = f"[{kind}]"
    t = ti.group(1).strip() if ti else ""
    d = de.group(1).strip() if de else ""
    if t: s += " " + t
    if d and d != t: s += f" — {d}"
    if url and kind in ("链接", "文章"): s += f"  {url.group(1)}"
    return s

def render(lt, c):
    if lt == 1: return re.sub(r"[\x01\x02]", "", c).strip()
    if lt == 3: return "[图片]"
    if lt == 34: return "[语音]"
    if lt == 43: return "[视频]"
    if lt == 42: return "[名片]"
    if lt == 47: return "[表情]"
    if lt == 48: return "[位置]"
    if lt in (10000, 10002): return "[系统] " + re.sub(r"<[^>]+>", "", c).strip()
    if lt == 50: return "[语音通话]"
    if "<appmsg" in c or "<title>" in c or "<finderFeed>" in c: return app_card(c)
    if lt in (4194304528, 4194304529): return "[视频号]"
    if c.strip().startswith("[") and len(c) < 20: return c.strip()
    return f"[消息type{lt}]"

def chatlab_type(lt, c):
    if lt == 1: return "文本消息"
    if lt == 3: return "图片消息"
    if lt == 34: return "语音消息"
    if lt == 43: return "视频消息"
    if lt == 47: return "动画表情"
    if lt == 42: return "名片消息"
    if lt == 48: return "位置消息"
    if lt == 10000 or lt == 10002: return "文本消息"
    if lt == 50: return "文本消息"
    if "<appmsg" in c or "<title>" in c or "<finderFeed>" in c:
        ty = re.search(r"<type>(\d+)</type>", c)
        t = ty.group(1) if ty else ""
        if t == "5" or t == "44": return "卡片式链接"
        if t == "6" or t == "2000": return "文件消息"
        if t == "33" or t == "36" or t == "62" or "<finderFeed>" in c: return "小程序分享"
        return "图文消息"
    return "文本消息"

messages = []
skipped = 0
for r in uniq:
    wxid = r["_n2i"].get(r.get("real_sender_id")) or n2i_all.get(r.get("real_sender_id"), "")
    if not wxid:
        # 解析不到发言人: 群消息里这类几乎都是本账号自己发的(如自己发的红包/转账),
        # 归到本账号以免 ChatLab 丢弃该条消息。
        wxid = self_user or "unknown_sender"
        display = "我" if self_user else "未知"
        is_send = 1
    elif wxid.endswith("@chatroom"):
        skipped += 1; continue  # 群级系统消息，解析器会丢弃
    else:
        display = names.get(wxid) or f"?{r.get('real_sender_id')}"
        is_send = 1 if (self_user and wxid == self_user) else 0
    # 解码正文
    raw = r.get("message_content")
    if r.get("WCDB_CT_message_content") == 4 and isinstance(raw, (bytes, bytearray)):
        c = zdecomp(bytes(raw)).decode("utf-8", "replace")
    elif isinstance(raw, (bytes, bytearray)):
        c = raw.decode("utf-8", "replace")
    else:
        c = raw or ""
    # 群文本前缀 "wxid_xxx: 正文" 剥离，senderUsername 已承载发言人
    if c.startswith(("wxid_", SELF_WXID, "bin0")) and ":" in c[:40]:
        c = re.sub(r"^[A-Za-z0-9_\-]+\s*:\s*", "", c)
    body = render(r.get("local_type"), c).replace("\n", "  \n")
    messages.append({
        "senderUsername": wxid,
        "senderDisplayName": display,
        "senderAvatarKey": wxid,
        "createTime": int(r["create_time"]),
        "type": chatlab_type(r.get("local_type"), c),
        "content": body,
        "isSend": is_send,
    })

print(f"生成消息 {len(messages)} 条 (跳过群级系统消息 {skipped} 条)")

# ---------- 4. 组装 echotrace JSON ----------
# 注意：chatlab-cli 导入 echotrace 时复用的是 WeFlow 解析器，会话名/类型只认
#   session.type（中文「私聊」/「群聊」）、session.wxid（不以 @chatroom 结尾→private）、
#   session.displayName || session.nickname；
# 只写 session.chatType 会被落成 type=group，且 name 退化成导入文件名（带 _ChatLab 后缀）。
# chatInfo 放最前，兼容按 chatInfo 取会话名的解析分支。
session = {
    "type": "群聊" if chat_kind == "group" else "私聊",
    "wxid": group_id,
    "displayName": group_name,
    "nickname": session_nick or group_name,
    "chatType": chat_kind,
    "groupId": group_id,
}
chat_info = {"name": group_name, "type": chat_kind, "id": group_id}
doc = {"chatInfo": chat_info, "session": session, "messages": messages}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)

db_size = os.path.getsize(OUT) / 1024
t0 = datetime.datetime.fromtimestamp(uniq[0]["create_time"])
t1 = datetime.datetime.fromtimestamp(uniq[-1]["create_time"])
last_ts = int(uniq[-1]["create_time"])

# 先算增量，再写状态（否则上次记录已被覆盖）
new_cnt, prev_date = _state.delta_summary(group_id, messages)
_state.record_export(group_id, group_name, len(messages), last_ts, OUT)

nmc = collections.Counter(m["senderDisplayName"] for m in messages)
print(f"\n[OK] {os.path.abspath(OUT)}")
print(f"   {'群' if chat_kind == 'group' else '私聊'}: {group_name} ({group_id})")
print(f"   导出日期: {_state.today()}")
print(f"   时间范围: {t0:%Y-%m-%d %H:%M} ~ {t1:%Y-%m-%d %H:%M}")
print(f"   消息: {len(messages)} 条, 发言人 {len(nmc)} 人")
print(f"   文件大小: {db_size:.0f} KB")
print(f"   我的消息(isSend=1): {sum(1 for m in messages if m['isSend']==1)} 条")
if new_cnt is None:
    print("   增量: 首次导出（无历史记录），导入时会新建会话")
elif new_cnt == 0:
    print(f"   增量: 相比上次({prev_date}) 无新消息（导入只做去重校验）")
else:
    print(f"   增量: 相比上次({prev_date}) 新增 {new_cnt} 条（导入时自动并入原会话）")
print(f"   本月 TOP: {nmc.most_common(8)}")
