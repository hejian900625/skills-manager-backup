#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
导出 QQ NT 全部群聊的「基本信息」（不含聊天记录）。

数据源（已由 qq-nt-decrypt 解密出的明文库）：
  qq_out/group_info_plain.db
    - group_list            : 群列表（群号/群名/长号/成员数/上限/备注/分类码）
    - group_detail_info_ver1: 群详情（群主uid/加群问题/等级码 等）

输出：
  qq_out/qq_groups.csv  —— 扁平表（Excel 友好 utf-8-sig）
  qq_out/qq_groups.html —— 自包含浏览表格

字段说明（QQ NT 新版，列名为数字 ID，版本敏感）：
  60001 群号         60007 群名称
  60221 群标识码/长号 60006 成员数（群资料声明值）
  60005 成员上限     60004 群分类码（平台内部枚举，含义随版本）
  60002 群主UID(u_ 格式，QQ NT 新 uid 方案)
  60224 加群验证问题 60026 备注
"""
import sqlite3, csv, html, datetime, os, json, sys

OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qq_out")
DB = os.path.join(OUTDIR, "group_info_plain.db")

def fmt_ts(v):
    try:
        v = int(v)
        if v <= 0 or v < 1_000_000_000:   # 非合理 Unix 秒
            return ""
        return datetime.datetime.utcfromtimestamp(v).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""

def load_nickname_sources(outdir):
    """返回 (uid->昵称, (群号,uid)->昵称)。优先 profile_info_v6 通用档案缓存，
    回退 group_member3 缓存成员名单。二者都缺的群主只剩 u_ uid，需联网查询。"""
    prof = {}
    mem = {}
    pp = os.path.join(outdir, "profile_info_plain.db")
    if os.path.exists(pp):
        p = sqlite3.connect(pp)
        try:
            for uid, name in p.execute('SELECT "1000","20002" FROM profile_info_v6').fetchall():
                if uid and name:
                    prof[uid] = name
        except Exception:
            pass
        p.close()
    gi = os.path.join(outdir, "group_info_plain.db")
    if os.path.exists(gi):
        g = sqlite3.connect(gi)
        try:
            for gid, uid, name in g.execute('SELECT "60001","1000","20002" FROM group_member3').fetchall():
                if gid and uid and name:
                    mem[(gid, uid)] = name
        except Exception:
            pass
        g.close()
    return prof, mem


def main():
    if not os.path.exists(DB):
        sys.exit(f"未找到解密库: {DB}\n请先运行 qq-nt-decrypt 的 decrypt_all.py 解密 nt_db。")
    con = sqlite3.connect(DB)
    cur = con.cursor()
    prof, mem = load_nickname_sources(OUTDIR)

    # group_list 基础字段
    list_cols = {
        "60001": "群号", "60007": "群名称", "60221": "群标识码(长号)",
        "60006": "成员数", "60005": "成员上限", "60004": "群分类码",
        "60026": "备注",
    }
    # 60001 作为连接键，不参与输出列
    detail_cols = {
        "60001": "_gid", "60002": "群主UID", "60224": "加群验证问题",
        "60205": "等级码", "60206": "等级分",
    }

    def cols_str(d):
        return ", ".join(f'"{k}"' for k in d)

    list_rows = cur.execute(
        f'SELECT {cols_str(list_cols)} FROM group_list'
    ).fetchall()
    # detail 用 dict 索引（以 60001 为 key）
    det_rows = cur.execute(
        f'SELECT {cols_str(detail_cols)} FROM group_detail_info_ver1'
    ).fetchall()
    det_idx = {r[0]: r for r in det_rows}  # 60001 -> row

    recs = []
    for lr in list_rows:
        d = dict(zip(list_cols.keys(), lr))
        gid = d["60001"]
        dr = det_idx.get(gid)
        rec = {
            "群号": gid,
            "群名称": d["60007"] or "",
            "群标识码(长号)": d["60221"] or "",
            "成员数": d["60006"] if d["60006"] is not None else "",
            "成员上限": d["60005"] if d["60005"] is not None else "",
            "群分类码": d["60004"] if d["60004"] is not None else "",
            "备注": d["60026"] or "",
            "群主昵称": "", "群主UID": "", "加群验证问题": "", "等级码": "", "等级分": "",
        }
        if dr:
            dd = dict(zip(detail_cols.keys(), dr))
            owner_uid = dd["60002"] or ""
            rec["群主UID"] = owner_uid
            rec["群主昵称"] = prof.get(owner_uid) or mem.get((gid, owner_uid)) or ""
            rec["加群验证问题"] = dd["60224"] or ""
            rec["等级码"] = dd["60205"] if dd["60205"] is not None else ""
            rec["等级分"] = dd["60206"] if dd["60206"] is not None else ""
        recs.append(rec)

    # 排序：按成员数降序，便于看大群
    recs.sort(key=lambda r: (int(r["成员数"]) if str(r["成员数"]).isdigit() else 0), reverse=True)

    fields = ["群号", "群名称", "群标识码(长号)", "成员数", "成员上限",
              "群主昵称", "群主UID", "加群验证问题", "等级码", "等级分", "群分类码", "备注"]

    csv_path = os.path.join(OUTDIR, "qq_groups.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            w.writerow(r)

    html_path = os.path.join(OUTDIR, "qq_groups.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(render_html(recs, fields))

    con.close()
    print(f"导出完成：{len(recs)} 个群")
    print(f"  CSV : {csv_path}")
    print(f"  HTML: {html_path}")


def render_html(recs, fields):
    rows = []
    for r in recs:
        tds = "".join(f"<td>{html.escape(str(r.get(fld, '')))}</td>" for fld in fields)
        rows.append(f"<tr>{tds}</tr>")
    head = "".join(f"<th>{html.escape(f)}</th>" for f in fields)
    data = json.dumps(recs, ensure_ascii=False)
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>QQ 群聊基本信息</title>
<style>
*{{box-sizing:border-box}}
body{{font-family:-apple-system,'Segoe UI',Roboto,'Microsoft YaHei',sans-serif;margin:0;background:#f5f6f8;color:#222}}
header{{padding:18px 22px;background:#2b6cb0;color:#fff}}
header h1{{margin:0;font-size:19px}}
header p{{margin:4px 0 0;opacity:.85;font-size:13px}}
.wrap{{padding:16px 22px}}
.bar{{display:flex;gap:10px;margin-bottom:12px}}
.bar input{{flex:1;padding:9px 12px;border:1px solid #ccd; border-radius:8px;font-size:14px}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.08)}}
th,td{{padding:9px 11px;border-bottom:1px solid #eef;text-align:left;font-size:13px;vertical-align:top}}
th{{background:#eef3fb;position:sticky;top:0;cursor:pointer;user-select:none}}
tr:hover td{{background:#f5f9ff}}
.tag{{display:inline-block;background:#e8f0fe;color:#1a56a8;border-radius:6px;padding:1px 7px;font-size:12px}}
</style></head><body>
<header><h1>QQ 群聊基本信息（共 {len(recs)} 个群）</h1>
<p>来源：本机 QQ NT 解密库 group_info_plain.db · 不含聊天记录</p></header>
<div class="wrap">
<div class="bar"><input id="q" placeholder="搜索群号 / 群名 / 群主UID / 备注 ..."></div>
<table id="t"><thead><tr>{head}</tr></thead><tbody id="b">{"".join(rows)}</tbody></table>
</div>
<script>
const DATA={data};
const F={json.dumps(fields,ensure_ascii=False)};
const tb=document.getElementById('b'), q=document.getElementById('q');
function draw(filter){{
  tb.innerHTML=DATA.filter(r=>!filter||F.some(f=>(r[f]??'').toString().toLowerCase().includes(filter))).map(r=>'<tr>'+F.map(f=>'<td>'+String(r[f]??'').replace(/[<>&]/g,c=>({{'<':'&lt;','>':'&gt;','&':'&amp;'}})[c])+'</td>').join('')+'</tr>').join('');
}}
q.oninput=()=>draw(q.value.trim().toLowerCase());
draw('');
</script></body></html>"""


if __name__ == "__main__":
    main()
