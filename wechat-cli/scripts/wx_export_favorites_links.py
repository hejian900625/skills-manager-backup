#!/usr/bin/env python3
"""微信收藏 · 链接/文章专项导出（type=5）。

与 wx_export_favorites.py 的区别：那个导全部 613 条，这个只导链接/文章，
并做域名归类、公众号统计、年份/标签维度聚合。

注意：链接条目的摘要字段是 <pagedesc>，**不是** <desc>（desc 是文本/聊天记录用的）。
公众号名在 <appmsgshareitem><srcdisplayname>，213/374 条有。

用法:
  python wx_export_favorites_links.py --db <favorite.db> --out wx_export
"""
import argparse
import collections
import datetime
import os
import re
import sqlite3
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wx_export_favorites import parse_content, unescape  # noqa: E402

# 链接类条目的补充字段（parse_content 的 WANT 里没有这几个）
LINK_WANT = {'pagedesc', 'clean_url', 'pagethumb_url', 'srcdisplayname',
             'srcusername', 'brandid', 'pubtime', 'duration'}


def parse_link(raw):
    """在通用解析基础上，补抓链接专用字段。"""
    import html.parser

    class P(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack, self.data = [], {}

        def handle_starttag(self, tag, attrs):
            self.stack.append(tag)
            for k, v in attrs:
                if k in ('brandid', 'pubtime'):
                    self.data.setdefault(k, []).append(v)

        def handle_endtag(self, tag):
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()

        def handle_data(self, text):
            if self.stack and self.stack[-1] in LINK_WANT:
                t = text.strip()
                if t:
                    self.data.setdefault(self.stack[-1], []).append(t)

    p = P()
    try:
        p.feed(raw or '')
    except Exception:
        pass
    out = {k: v[0] for k, v in p.data.items() if v}
    # pagedesc 可能被切分多段，拼接更完整
    if p.data.get('pagedesc'):
        out['pagedesc'] = ''.join(p.data['pagedesc'])
    return out


def domain_of(url):
    try:
        d = urllib.parse.urlparse(url).netloc.lower()
        return d[4:] if d.startswith('www.') else d
    except Exception:
        return ''


def host_kind(dom):
    """把域名归成大类。"""
    if not dom:
        return '未知'
    if dom.endswith('weixin.qq.com') or 'qq.com' in dom:
        return '微信公众号'
    if 'xiaohongshu' in dom or 'xhslink' in dom:
        return '小红书'
    if 'zhihu' in dom:
        return '知乎'
    if 'douban' in dom:
        return '豆瓣'
    if 'weibo' in dom:
        return '微博'
    if 'csdn' in dom:
        return 'CSDN'
    if 'jianshu' in dom or 'juejin' in dom:
        return '掘金/简书'
    if 'bilibili' in dom:
        return 'B站'
    if 'douyin' in dom:
        return '抖音'
    return '其他'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='wx_decrypted2/favorite/favorite.db')
    ap.add_argument('--out', default='wx_export')
    ap.add_argument('--year', default=None, help='只导出某年份')
    ap.add_argument('--domain', default=None, help='只导出某域名（子串匹配）')
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row

    tag_map = {r['local_id']: r['name'] for r in con.execute('SELECT * FROM fav_tag_db_item')}
    bind = {}
    for r in con.execute('SELECT tag_local_id, fav_local_id FROM fav_bind_tag_db_item'):
        bind.setdefault(r['fav_local_id'], []).append(tag_map.get(r['tag_local_id'], '?'))

    rows = [dict(r) for r in
            con.execute('SELECT * FROM fav_db_item WHERE type=5 ORDER BY update_time DESC')]

    items = []
    for r in rows:
        base = parse_content(r.get('content'))
        extra = parse_link(r.get('content'))
        d = dict(base)
        d.update({k: v for k, v in extra.items() if v and not d.get(k)})
        url = d.get('link') or d.get('weburl') or d.get('clean_url') or ''
        dom = domain_of(url)
        items.append({
            'time': r['update_time'],
            'title': unescape(d.get('pagetitle') or d.get('title') or '(无标题)'),
            'summary': unescape(d.get('pagedesc') or d.get('desc') or ''),
            'url': url,
            'domain': dom,
            'kind': host_kind(dom),
            'account': unescape(d.get('srcdisplayname') or ''),
            'srcuser': d.get('srcusername') or '',
            'tags': bind.get(r['local_id'], []),
            'fromusr': r.get('fromusr') or '',
            'chat': r.get('realchatname') or '',
        })

    if args.year:
        items = [i for i in items
                 if datetime.datetime.fromtimestamp(i['time']).strftime('%Y') == args.year]
    if args.domain:
        items = [i for i in items if args.domain in i['domain']]

    L = []
    yr = collections.Counter(
        datetime.datetime.fromtimestamp(i['time']).strftime('%Y') for i in items)
    kc = collections.Counter(i['kind'] for i in items)

    L.append('# 微信收藏 · 链接/文章')
    L.append('')
    L.append(f'- 链接类条目：**{len(items)}** 条（收藏总数 613 条中的一部分）')
    L.append(f'- 时间跨度：{min(yr)} ~ {max(yr)}')
    L.append(f'- 有摘要的：{sum(1 for i in items if i["summary"])} 条')
    L.append(f'- 有公众号名的：{sum(1 for i in items if i["account"])} 条')
    L.append(f'- 导出时间：{datetime.datetime.now():%Y-%m-%d %H:%M}')
    L.append('')

    # ---- 年份分布 ----
    L.append('## 年份分布')
    L.append('')
    L.append('| 年份 | 数量 | 占比 |')
    L.append('| --- | --- | --- |')
    tot = len(items) or 1
    for k in sorted(yr):
        L.append(f'| {k} | {yr[k]} | {yr[k]/tot*100:.1f}% |')
    L.append('')

    # ---- 平台分布 ----
    L.append('## 平台分布')
    L.append('')
    L.append('| 平台 | 数量 | 占比 |')
    L.append('| --- | --- | --- |')
    for k, v in kc.most_common():
        L.append(f'| {k} | {v} | {v/tot*100:.1f}% |')
    L.append('')

    # ---- 域名 TOP ----
    dc = collections.Counter(i['domain'] for i in items if i['domain'])
    L.append('## 域名 TOP 20')
    L.append('')
    L.append('| 域名 | 数量 |')
    L.append('| --- | --- |')
    for k, v in dc.most_common(20):
        L.append(f'| {k} | {v} |')
    L.append('')

    # ---- 公众号 TOP ----
    ac = collections.Counter(i['account'] for i in items if i['account'])
    if ac:
        L.append('## 公众号 TOP 20')
        L.append('')
        L.append('| 公众号 | 收藏数 |')
        L.append('| --- | --- |')
        for k, v in ac.most_common(20):
            L.append(f'| {k} | {v} |')
        L.append('')

    # ---- 标签 ----
    tc = collections.Counter(t for i in items for t in i['tags'])
    if tc:
        L.append('## 标签分布')
        L.append('')
        L.append('| 标签 | 条数 |')
        L.append('| --- | --- |')
        for k, v in tc.most_common():
            L.append(f'| {k} | {v} |')
        L.append('')

    # ---- 明细表（倒序，最新在前）----
    L.append('## 明细索引')
    L.append('')
    L.append('| # | 收藏日期 | 平台 | 标题 | 公众号/作者 | 域名 |')
    L.append('| --- | --- | --- | --- | --- | --- |')
    for n, i in enumerate(items, 1):
        d = datetime.datetime.fromtimestamp(i['time']).strftime('%Y-%m-%d')
        t = i['title'].replace('|', '\\|').replace('\n', ' ')
        t = t[:64] + ('…' if len(t) > 64 else '')
        L.append(f"| {n} | {d} | {i['kind']} | {t} | "
                 f"{i['account'] or '—'} | {i['domain'] or '—'} |")
    L.append('')
    L.append('---')
    L.append('')

    # ---- 完整条目 ----
    L.append('## 完整条目')
    L.append('')
    for n, i in enumerate(items, 1):
        d = datetime.datetime.fromtimestamp(i['time']).strftime('%Y-%m-%d %H:%M')
        L.append(f"### {n}. {i['title']}")
        L.append('')
        L.append(f"- 收藏时间：{d}")
        L.append(f"- 平台：{i['kind']}（{i['domain'] or '—'}）")
        if i['account']:
            L.append(f"- 公众号：{i['account']}")
        if i['tags']:
            L.append(f"- 标签：{', '.join(i['tags'])}")
        if i['chat']:
            L.append(f"- 来源聊天：{i['chat']}")
        L.append(f"- 链接：{i['url']}")
        if i['summary']:
            L.append('')
            L.append(f"> {i['summary']}")
        L.append('')

    os.makedirs(args.out, exist_ok=True)
    suffix = f'_{args.year}' if args.year else ''
    suffix += f'_{args.domain.replace(".", "")}' if args.domain else ''
    dst = os.path.join(args.out, f'微信收藏_链接文章{suffix}.md')
    txt = '\n'.join(L)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write(txt)
    print(f'[OK] {len(items)} 条链接 -> {dst}')
    print(f'     {len(txt.splitlines())} 行, {len(txt)/1024:.0f} KB')
    print()
    print('年份:', dict(sorted(yr.items())))
    print('平台:', dict(kc.most_common()))
    print(f'有摘要: {sum(1 for i in items if i["summary"])}, '
          f'有公众号: {sum(1 for i in items if i["account"])}')


if __name__ == '__main__':
    main()