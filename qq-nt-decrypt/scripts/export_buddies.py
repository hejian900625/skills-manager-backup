#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出 QQ NT 好友列表（基本信息，不含聊天记录）。
数据来自解密后的 profile_info_plain.db：
  - buddy_list      : 好友 uid 列表 + 备注 + 分组ID
  - profile_info_v6 : 通用档案缓存，反查 uid -> 昵称 / 个性签名 / 备注
注意：QQ NT 用 u_xxx uid 代替数字 QQ 号，本机缓存不含数字 QQ 号，故无法导出短号。
用法:
  python qq_export_buddies.py --outdir qq_out
依赖: 已用 qq-nt-decrypt 的 decrypt_all.py 解密出 profile_info_plain.db
"""
import argparse
import csv
import html
import os
import sqlite3
import sys

DB = "qq_out/profile_info_plain.db"


def escape(v):
    return html.escape(str(v)) if v is not None else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default="qq_out")
    ap.add_argument("--db", default=DB)
    args = ap.parse_args()

    db = args.db
    if not os.path.exists(db):
        sys.exit(f"未找到解密库: {db}\n请先运行 qq-nt-decrypt 的 decrypt_all.py 解密 nt_db（含 profile_info.db）。")

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    con = sqlite3.connect(db)
    cur = con.cursor()

    # 通用档案缓存: uid -> (昵称, 个性签名, 备注)
    prof = {}
    try:
        for uid, nick, sign, remark in cur.execute(
            'SELECT "1000","20002","20011","1001" FROM profile_info_v6'
        ).fetchall():
            prof[uid] = (nick or "", sign or "", remark or "")
    except Exception as e:
        print(f"[warn] profile_info_v6 读取失败: {e}", file=sys.stderr)

    # 好友列表
    rows = cur.execute(
        'SELECT "1000","1001","1002","25007" FROM buddy_list'
    ).fetchall()

    recs = []
    for uid, remark_bl, cat_id, f25007 in rows:
        nick = ""
        sign = ""
        remark_prof = ""
        if uid in prof:
            nick, sign, remark_prof = prof[uid]
        # 备注优先用 buddy_list 的，其次 profile 的
        remark = remark_bl or remark_prof or ""
        recs.append({
            "好友UID": uid or "",
            "昵称": nick,
            "备注": remark,
            "个性签名": sign,
            "分组ID": cat_id if cat_id is not None else "",
        })

    # 按昵称排序（无昵称的排后面），保持可读
    recs.sort(key=lambda r: (r["昵称"] == "", r["昵称"], r["好友UID"]))

    fields = ["好友UID", "昵称", "备注", "个性签名", "分组ID"]
    csv_path = os.path.join(outdir, "qq_buddies.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            w.writerow(r)

    # HTML 自包含查看器
    html_rows = "\n".join(
        f"<tr><td>{escape(r['好友UID'])}</td><td>{escape(r['昵称'])}</td>"
        f"<td>{escape(r['备注'])}</td><td>{escape(r['个性签名'])}</td>"
        f"<td>{escape(r['分组ID'])}</td></tr>"
        for r in recs
    )
    html_doc = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QQ NT 好友列表</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,"Microsoft YaHei",sans-serif;margin:0;background:#f5f6f8;color:#222}}
header{{padding:16px 20px;background:#fff;border-bottom:1px solid #e5e7eb}}
h1{{margin:0;font-size:18px}}
.sub{{color:#6b7280;font-size:13px;margin-top:4px}}
.bar{{padding:10px 20px;background:#fff;border-bottom:1px solid #e5e7eb}}
input{{width:100%;max-width:420px;padding:8px 10px;border:1px solid #d1d5db;border-radius:8px;font-size:14px}}
table{{width:100%;border-collapse:collapse;background:#fff}}
th,td{{padding:9px 14px;text-align:left;border-bottom:1px solid #eef0f2;font-size:14px;vertical-align:top}}
th{{background:#f9fafb;position:sticky;top:0;cursor:pointer;user-select:none}}
tbody tr:hover{{background:#f3f7ff}}
.uid{{font-family:monospace;color:#6b7280;font-size:12px}}
.sig{{color:#6b7280;font-size:13px}}
.empty{{padding:40px;text-align:center;color:#9ca3af}}
</style></head>
<body>
<header><h1>QQ NT 好友列表</h1>
<div class="sub">共 {len(recs)} 位好友 · 数据来自本机 profile_info_plain.db · 不含聊天记录 · 不含数字QQ号（NT架构用u_xxx uid）</div></header>
<div class="bar"><input id="q" placeholder="搜索昵称 / 备注 / 个性签名 / uid ..."></div>
<table><thead><tr>
<th>好友UID</th><th>昵称</th><th>备注</th><th>个性签名</th><th>分组ID</th>
</tr></thead><tbody id="tb">
{html_rows}
</tbody></table>
<div class="empty" id="empty" style="display:none">无匹配结果</div>
<script>
const q=document.getElementById('q'),tb=document.getElementById('tb'),empty=document.getElementById('empty');
const rows=[...tb.children];
q.addEventListener('input',()=>{{
  const t=q.value.trim().toLowerCase();let n=0;
  rows.forEach(r=>{{const m=r.textContent.toLowerCase().includes(t);r.style.display=m?'':'none';if(m)n++;}});
  empty.style.display=n?'none':'block';
}});
</script>
</body></html>"""
    html_path = os.path.join(outdir, "qq_buddies.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)

    named = sum(1 for r in recs if r["昵称"])
    print(f"[ok] 导出 {len(recs)} 位好友 -> {csv_path}")
    print(f"     含昵称: {named}/{len(recs)}")
    print(f"     文件: {csv_path}")
    print(f"           {html_path}")


if __name__ == "__main__":
    main()
