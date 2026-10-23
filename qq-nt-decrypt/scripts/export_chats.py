#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析解密后的 QQ NT 数据库，导出聊天记录为 CSV + 自包含 HTML 查看器。

列映射（QQ NT 新版，列名是数字 ID，版本敏感）:
    40001  消息 id
    40010  会话类型 (1=私聊 c2c, 2=群聊 group)
    40011  消息类型
    40020  发送者 uid
    40090  发送者昵称
    40021 / 40027  对端/群 uin
    40050  发送时间 (unix 秒)
    40800  内容 BLOB（protobuf，内含 UTF-8 文本片段）

内容 BLOB 用通用 protobuf walker 抽取 UTF-8 文本（含 emoji/CJK 判定）。
群名从 group_info_plain.db 的 group_list 解析（60001/60221 作 uin key，60007 作名称）。
非文本（图片/文件/表情）在内容列标为 [非文本消息]。

用法:
    python export_chats.py --outdir qq_out
    python export_chats.py --outdir qq_out --csv out.csv --html out.html
"""
import argparse
import csv
import datetime
import glob
import json
import os
import sqlite3

# ---------- protobuf 通用字符串 walker ----------
def read_varint(buf, i):
    shift = 0; result = 0
    while True:
        b = buf[i]; i += 1
        result |= (b & 0x7f) << shift
        if not (b & 0x80):
            return result, i
        shift += 7


def is_utf8_text(b):
    if not b or len(b) > 4096:
        return None
    try:
        s = b.decode("utf-8")
    except Exception:
        return None
    if "\x00" in s:
        return None
    if not any((0x20 <= ord(c) < 0x7f) or (0x4e00 <= ord(c) <= 0x9fff)
               or (0x3000 <= ord(c) <= 0x303f) or (0xff00 <= ord(c) <= 0xffef) for c in s):
        return None
    return s


def walk(buf, depth=0, out=None):
    if out is None:
        out = []
    i = 0; n = len(buf)
    while i < n:
        tag, i = read_varint(buf, i)
        field = tag >> 3; wt = tag & 7
        if wt == 0:
            _, i = read_varint(buf, i)
        elif wt == 2:
            ln, i = read_varint(buf, i)
            if i + ln > n:
                break
            sub = buf[i:i + ln]; i += ln
            s = is_utf8_text(sub)
            if s is not None:
                out.append(s)
            if depth < 6:
                try:
                    walk(sub, depth + 1, out)
                except Exception:
                    pass
        elif wt == 5:
            i += 4
        elif wt == 1:
            i += 8
        else:
            break
    return out


def extract_text(blob):
    if not blob:
        return ""
    strings = walk(blob)
    cleaned = [s for s in strings if not s.startswith("u_")]
    if not cleaned:
        return ""
    seen = set(); res = []
    for s in cleaned:
        if s not in seen:
            seen.add(s); res.append(s)
    return " ".join(res)


def fmt(ts):
    if not ts or ts <= 0:
        return ""
    dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=ts + 8 * 3600)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def main():
    ap = argparse.ArgumentParser(description="导出 QQ NT 聊天记录")
    ap.add_argument("--outdir", default="qq_out", help="解密输出目录（含 *_plain.db）")
    ap.add_argument("--csv", default=None, help="CSV 输出路径")
    ap.add_argument("--html", default=None, help="HTML 输出路径")
    ap.add_argument("--msgtable", default="nt_msg_plain.db", help="主消息库文件名")
    ap.add_argument("--groupdb", default="group_info_plain.db", help="群信息库文件名")
    args = ap.parse_args()

    OUT = args.outdir
    NT = os.path.join(OUT, args.msgtable)
    GROUP_DB = os.path.join(OUT, args.groupdb)
    CSV = args.csv or os.path.join(OUT, "qq_messages.csv")
    HTML = args.html or os.path.join(OUT, "qq_chat.html")

    if not os.path.exists(NT):
        print(f"未找到主消息库: {NT}\n请先运行 decrypt_all.py 解密。", file=__import__("sys").stderr)
        __import__("sys").exit(2)

    # ---------- 群名映射 ----------
    group_names = {}
    if os.path.exists(GROUP_DB):
        g = sqlite3.connect(GROUP_DB)
        try:
            cols = [r[1] for r in g.execute('PRAGMA table_info("group_list")').fetchall()]
            if {"60001", "60007"}.issubset(set(cols)) or all(c in cols for c in ("60001", "60007")):
                for row in g.execute('SELECT "60001","60221","60007" FROM group_list'):
                    code, full, name = row
                    for k in (code, full):
                        if k is not None:
                            group_names[str(k)] = name or str(k)
        except Exception:
            pass
        g.close()

    # ---------- 读消息 ----------
    p = sqlite3.connect(NT)
    tables = [r[0] for r in p.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%msg_table'").fetchall()]

    REQ = ["40001", "40010", "40011", "40020", "40090", "40021", "40027", "40050", "40800"]
    records = []
    for tab in tables:
        cols = [r[1] for r in p.execute(f'PRAGMA table_info("{tab}")').fetchall()]
        if "40001" not in cols:
            continue
        qcols = [c for c in REQ if c in cols]
        if not qcols:
            continue
        sql = 'SELECT ' + ','.join(f'"{c}"' for c in qcols) + f' FROM "{tab}"'
        for row in p.execute(sql):
            rm = dict(zip(qcols, row))
            chat_type = rm.get("40010")
            sender_uid = rm.get("40020")
            sender_nick = rm.get("40090") or ""
            peer = rm.get("40021") or str(rm.get("40027") or "")
            ts = rm.get("40050") or 0
            blob = rm.get("40800")
            text = extract_text(blob)
            ctype = "text" if text else "other"
            if chat_type == 2:
                peer_name = group_names.get(str(peer), peer)
                ctype_label = "群聊"
            else:
                peer_name = peer
                ctype_label = "私聊" if chat_type == 1 else f"类型{chat_type}"
            if not text:
                text = "[非文本消息]"
            records.append({
                "ts": ts, "chat_type": chat_type,
                "sender_uid": sender_uid or "", "sender_nick": sender_nick,
                "peer": str(peer), "peer_name": peer_name,
                "ctype_label": ctype_label, "ctype": ctype, "text": text,
            })
    p.close()
    records.sort(key=lambda r: r["ts"] if r["ts"] and r["ts"] > 0 else 0)

    # ---------- CSV ----------
    with open(CSV, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["时间", "类型", "对端ID", "对端名称", "发送者UID", "发送者昵称", "内容类型", "内容"])
        for r in records:
            w.writerow([fmt(r["ts"]), r["ctype_label"], r["peer"], r["peer_name"],
                        r["sender_uid"], r["sender_nick"], r["ctype"], r["text"]])
    print(f"[csv] 写出 {len(records)} 条 -> {os.path.basename(CSV)}")

    # ---------- 会话聚合 ----------
    convs = {}
    for r in records:
        convs.setdefault((r["ctype_label"], r["peer"]), []).append(r)
    conv_list = []
    for (label, peer), msgs in convs.items():
        msgs.sort(key=lambda x: x["ts"] or 0)
        conv_list.append({
            "label": label, "peer": peer, "name": msgs[0]["peer_name"],
            "count": len(msgs), "first": fmt(msgs[0]["ts"]), "last": fmt(msgs[-1]["ts"]),
            "last_text": msgs[-1]["text"],
            "msgs": [{"t": fmt(m["ts"]), "nick": m["sender_nick"], "text": m["text"]} for m in msgs],
        })
    conv_list.sort(key=lambda c: c["msgs"][-1]["t"] if c["msgs"] else "", reverse=True)
    payload = json.dumps(conv_list, ensure_ascii=False)

    html_doc = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QQ NT 聊天记录导出</title>
<style>
body{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f0f2f5;color:#1f1f1f}
.header{background:#07c160;color:#fff;padding:12px 16px;font-size:15px;position:sticky;top:0;z-index:5}
.layout{display:flex;height:calc(100vh - 44px)}
.side{width:300px;background:#fff;border-right:1px solid #e5e5e5;overflow-y:auto}
.side input{width:100%;box-sizing:border-box;padding:8px 10px;border:0;border-bottom:1px solid #eee;font-size:13px}
.item{padding:10px 12px;border-bottom:1px solid #f2f2f2;cursor:pointer}
.item:hover{background:#f7f7f7}
.item.active{background:#e8f7ee}
.item .n{font-size:14px;font-weight:600}
.item .m{font-size:12px;color:#888;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item .badge{display:inline-block;font-size:11px;color:#fff;background:#07c160;border-radius:3px;padding:0 4px;margin-right:4px}
.main{flex:1;overflow-y:auto;padding:16px}
.conv-title{font-size:16px;font-weight:700;margin-bottom:12px;position:sticky;top:0;background:#f0f2f5;padding-bottom:8px}
.msg{max-width:80%;margin:8px 0;padding:8px 12px;border-radius:8px;font-size:14px;line-height:1.5;word-break:break-word}
.other{background:#fff}
.meta{font-size:11px;color:#999;margin-bottom:3px}
.empty{color:#999;text-align:center;margin-top:40px}
</style></head>
<body>
<div class="header">QQ NT 聊天记录导出 · 共 <span id="cnt"></span> 个会话</div>
<div class="layout">
<div class="side"><input id="search" placeholder="搜索会话名称/内容..."><div id="list"></div></div>
<div class="main" id="main"><div class="empty">← 选择左侧会话查看记录</div></div>
</div>
<script>
const DATA = __PAYLOAD__;
const listEl=document.getElementById('list');
const mainEl=document.getElementById('main');
const searchEl=document.getElementById('search');
document.getElementById('cnt').textContent=DATA.length;
let active=null;
function render(filter){
  listEl.innerHTML='';
  const f=(filter||'').toLowerCase();
  DATA.forEach((c,i)=>{
    if(f && !(c.name.toLowerCase().includes(f)||c.peer.includes(f)||c.last_text.toLowerCase().includes(f))) return;
    const d=document.createElement('div');d.className='item'+(active===i?' active':'');
    d.innerHTML='<div class="n"><span class="badge">'+c.label+'</span>'+escapeHtml(c.name)+'</div>'+
                '<div class="m">'+escapeHtml(c.last_text)+' · '+c.count+'条 · '+c.last+'</div>';
    d.onclick=()=>{active=i;render(filter);show(c);};
    listEl.appendChild(d);
  });
}
function show(c){
  let h='<div class="conv-title">'+escapeHtml(c.name)+' <span style="font-size:12px;color:#888">('+c.label+', '+c.peer+', '+c.count+'条)</span></div>';
  c.msgs.forEach(m=>{
    h+='<div class="msg other"><div class="meta">'+escapeHtml(m.nick)+' · '+escapeHtml(m.t)+'</div>'+escapeHtml(m.text)+'</div>';
  });
  mainEl.innerHTML=h;mainEl.scrollTop=mainEl.scrollHeight;
}
function escapeHtml(s){return (s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
searchEl.oninput=e=>{active=null;render(e.target.value);mainEl.innerHTML='<div class="empty">← 选择左侧会话查看记录</div>';};
render('');
</script></body></html>""".replace("__PAYLOAD__", payload)

    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html_doc)
    print(f"[html] 写出 {len(conv_list)} 个会话 -> {os.path.basename(HTML)}")
    print(f"[done] 消息总数 {len(records)}")


if __name__ == "__main__":
    main()
