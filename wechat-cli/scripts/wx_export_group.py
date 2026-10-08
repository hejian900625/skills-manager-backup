# -*- coding: utf-8 -*-
import sys, os, json, hashlib, sqlite3, tempfile, datetime, collections, re
sys.path.insert(0, r'C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts')
import wcdb_key_tool_windows as W
import zstandard as zstd
ZC = zstd.ZstdDecompressor()
def zdecomp(b):
    try: return ZC.decompress(b)
    except Exception:
        try: return ZC.decompressobj().decompress(b)
        except Exception: return b

GROUP = sys.argv[1]
OUTNAME = sys.argv[2]
keys = json.load(open(r"C:/Users/Lenovo/.wechat-cli/all_keys.json", encoding="utf-8"))
dbdir = keys["_db_dir"]
TBL = "Msg_" + hashlib.md5(GROUP.encode()).hexdigest()
print(f"群: {GROUP}\n表: {TBL}\n" + "="*60)

# ---- 1. 遍历所有 message_N.db ----
all_rows = []
for fn in sorted(os.listdir(os.path.join(dbdir, "message"))):
    if not (fn.startswith("message_") and fn.endswith(".db") and fn.count("_") == 1):
        continue
    src = os.path.join(dbdir, "message", fn)
    rel = "message\\" + fn
    if rel not in keys: continue
    tmp = tempfile.mkdtemp(prefix="wxg_"); out = os.path.join(tmp, "p.db")
    if not W._decrypt_database(src, out, bytes.fromhex(keys[rel]["enc_key"])):
        continue
    con = sqlite3.connect(out); con.row_factory = sqlite3.Row
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

# ---- 2. 联系人名（需要所有库的 Name2Id？这里用全局 contact） ----
tmp = tempfile.mkdtemp(); cout = os.path.join(tmp, "c.db")
W._decrypt_database(os.path.join(dbdir, "contact", "contact.db"), cout,
                    bytes.fromhex(keys["contact\\contact.db"]["enc_key"]))
cc = sqlite3.connect(cout); cc.row_factory = sqlite3.Row
names = {}
for r in cc.execute("SELECT username, remark, nick_name, alias FROM contact"):
    names[r["username"]] = r["remark"] or r["nick_name"] or r["alias"] or r["username"]
names["hejian0625"] = "我"

# 群成员表（若有）
members = {}
try:
    for r in cc.execute("SELECT * FROM chatroom_member LIMIT 1"):
        pass
except Exception: pass

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

day = None; out = []
for r in uniq:
    dt = datetime.datetime.fromtimestamp(r["create_time"])
    d = dt.strftime("%Y-%m-%d")
    if d != day:
        out.append(f"\n## {d}\n"); day = d
    wxid = r["_n2i"].get(r.get("real_sender_id"), "")
    nm = names.get(wxid) or f"?{r.get('real_sender_id')}"
    raw = r.get("message_content")
    if r.get("WCDB_CT_message_content") == 4 and isinstance(raw, (bytes, bytearray)):
        c = zdecomp(bytes(raw)).decode("utf-8", "replace")
    elif isinstance(raw, (bytes, bytearray)):
        c = raw.decode("utf-8", "replace")
    else:
        c = raw or ""
    if c.startswith(("wxid_", "hejian", "bin0")) and ":" in c[:40]:
        c = re.sub(r"^[A-Za-z0-9_\-]+\s*:\s*", "", c)
    body = render(r.get("local_type"), c).replace("\n", "  \n")
    out.append(f"**{nm}** ({dt:%H:%M})：{body}")

t0 = datetime.datetime.fromtimestamp(uniq[0]["create_time"])
t1 = datetime.datetime.fromtimestamp(uniq[-1]["create_time"])
nmc = collections.Counter(names.get(r["_n2i"].get(r.get("real_sender_id"), ""), "?") for r in uniq)
hdr = f"""# {OUTNAME} · 群聊记录

- 群 ID：`{GROUP}`
- 时间范围：{t0:%Y-%m-%d %H:%M} ~ {t1:%Y-%m-%d %H:%M}
- 消息总数：**{len(uniq)} 条**
- 参与人数：{len(nmc)} 人
- 导出时间：{datetime.datetime.now():%Y-%m-%d %H:%M}

---
"""
dst = rf"D:/WorkBuddy/2026-09-29-14-04-17/wx_export/{OUTNAME}_群聊记录.md"
txt = hdr + "\n".join(out) + "\n"
open(dst, "w", encoding="utf-8").write(txt)
print(f"\n[OK] {dst}")
print(f"   {len(uniq)} 条, {len(txt.splitlines())} 行, {len(txt)/1024:.0f} KB")
print(f"   发言人: {nmc.most_common(12)}")
md = collections.Counter(datetime.datetime.fromtimestamp(r["create_time"]).strftime("%Y-%m") for r in uniq)
print("   月度:", " ".join(f"{k}:{md[k]}" for k in sorted(md)))
