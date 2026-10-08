#!/usr/bin/env python3
"""微信收藏导出 — 解析 favorite.db 的 fav_db_item.content XML。

用法:
  python wx_export_favorites.py [--db <favorite.db>] [--out <dir>] [--tag <标签名>]
"""
import argparse
import datetime
import html
import html.parser
import os
import re
import sqlite3
import xml.etree.ElementTree as ET

# 微信收藏 item type -> 中文名
TYPE_NAME = {
    1: '文本',
    2: '图片',
    3: '语音',
    4: '视频',
    5: '链接/文章',
    6: '位置',
    7: '音乐',
    8: '文件',
    14: '聊天记录',
    16: '视频(短视频)',
    18: '笔记',
}


class _FavParser(html.parser.HTMLParser):
    """宽容解析 favitem XML：抓 title/desc/pagetitle/link/weburl/label 等。"""

    WANT = {'title', 'desc', 'pagetitle', 'link', 'weburl', 'label', 'locitem',
            'datatitle', 'datadesc', 'datasrcname', 'datasrctime', 'duration',
            'sourcedatapath', 'msgDataPath'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.data = {}
        self.locs = []
        self.attrs_seen = {}
        self._cur_loc = None

    def handle_starttag(self, tag, attrs):
        self.stack.append(tag)
        if tag == 'locitem':
            self._cur_loc = dict(attrs)
        for k, v in attrs:
            if k in ('duration', 'datatype', 'subtype', 'fullsize'):
                self.attrs_seen.setdefault(k, []).append(v)

    def handle_endtag(self, tag):
        if tag == 'locitem' and self._cur_loc is not None:
            self.locs.append(self._cur_loc)
            self._cur_loc = None
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_data(self, text):
        if not self.stack:
            return
        tag = self.stack[-1]
        if tag in self.WANT:
            t = text.strip()
            if t:
                self.data.setdefault(tag, []).append(t)


def parse_content(raw):
    if not raw:
        return {}
    p = _FavParser()
    try:
        p.feed(raw)
    except Exception:
        pass
    out = {k: v[0] for k, v in p.data.items() if v}
    if p.data.get('desc'):
        out['desc'] = '\n'.join(p.data['desc'])
    if p.data.get('datadesc'):
        out['datadesc'] = '\n'.join(p.data['datadesc'])
    if p.locs:
        out['locs'] = p.locs
    if p.attrs_seen.get('duration'):
        out['duration'] = p.attrs_seen['duration'][0]
    return out


# 媒体条目兜底描述（无文字标题时按其属性生成）
MEDIA_HINT = {
    1: '文本片段（无正文记录）',
    2: '图片',
    3: '语音',
    4: '视频',
    6: '位置',
    7: '音乐',
    8: '文件',
    14: '聊天记录',
    16: '短视频',
    18: '笔记',
}


def item_label(item):
    """生成条目的展示标题，媒体类无文字时回退到类型名 + 属性。"""
    p = item['_parsed']
    for k in ('title', 'pagetitle', 'datatitle', 'label', 'desc', 'datadesc'):
        if p.get(k):
            return unescape(p[k])
    if p.get('locs'):
        lc = p['locs'][0]
        return '位置：' + (lc.get('label') or lc.get('poiname') or
                          f"{lc.get('lat')},{lc.get('lng')}")
    base = MEDIA_HINT.get(item['type'], item['_type_name'])
    extra = []
    if p.get('duration'):
        try:
            extra.append(f"{int(float(p['duration']))}秒")
        except (ValueError, TypeError):
            pass
    if p.get('sourcedatapath') or p.get('msgDataPath'):
        extra.append('有本地文件')
    return base + (f"（{', '.join(extra)}）" if extra else '')


def unescape(s):
    if not s:
        return ''
    s = html.unescape(s)
    s = s.replace('\r\n', '\n').replace('\r', '\n')
    s = re.sub(r'[\x00-\x08\x0b-\x1f]', '', s)
    return s.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='wx_decrypted/favorite/favorite.db')
    ap.add_argument('--out', default='wx_export')
    ap.add_argument('--tag', default=None, help='只导出某标签')
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row

    tag_map = {r['local_id']: r['name'] for r in con.execute('SELECT * FROM fav_tag_db_item')}
    bind = {}
    for r in con.execute('SELECT tag_local_id, fav_local_id FROM fav_bind_tag_db_item'):
        bind.setdefault(r['fav_local_id'], []).append(tag_map.get(r['tag_local_id'], '?'))

    rows = list(con.execute('SELECT * FROM fav_db_item ORDER BY update_time DESC'))
    items = []
    for r in rows:
        d = dict(r)
        d['_parsed'] = parse_content(d.get('content'))
        d['_tags'] = bind.get(d['local_id'], [])
        d['_type_name'] = TYPE_NAME.get(d['type'], f"type{d['type']}")
        items.append(d)

    if args.tag:
        items = [i for i in items if args.tag in i['_tags']]
        print(f'[标签 {args.tag}] {len(items)} 条')

    lines = ['# 微信收藏', '',
             f'- 收藏总数: **{len(items)}**',
             f'- 标签: ' + (', '.join(f'{k}({sum(1 for i in items if k in i["_tags"])})'
                                      for k in tag_map.values() if any(k in i['_tags'] for i in items)) or '无'),
             '']

    # 概览表
    import collections
    tc = collections.Counter(i['_type_name'] for i in items)
    lines.append('## 类型分布')
    lines.append('')
    lines.append('| 类型 | 数量 |')
    lines.append('| --- | --- |')
    for k, v in tc.most_common():
        lines.append(f'| {k} | {v} |')
    lines.append('')

    lines.append('## 收藏明细')
    lines.append('')
    lines.append('| # | 时间 | 类型 | 标题/内容 | 来源 | 标签 |')
    lines.append('| --- | --- | --- | --- | --- | --- |')

    def cell(s, n=70):
        s = unescape(str(s or '')).replace('|', '\\|').replace('\n', ' ')
        return s[:n] + ('…' if len(s) > n else '')

    for idx, i in enumerate(items, 1):
        p = i['_parsed']
        title = item_label(i)
        dt = datetime.datetime.fromtimestamp(i['update_time']).strftime('%Y-%m-%d')
        src = i.get('realchatname') or i.get('fromusr') or ''
        lines.append(f"| {idx} | {dt} | {i['_type_name']} | {cell(title)} | "
                     f"{cell(src, 20)} | {cell(','.join(i['_tags']), 14)} |")

    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('## 完整内容')
    lines.append('')

    for idx, i in enumerate(items, 1):
        p = i['_parsed']
        dt = datetime.datetime.fromtimestamp(i['update_time']).strftime('%Y-%m-%d %H:%M')
        lines.append(f"### {idx}. [{i['_type_name']}] {dt}")
        if i['_tags']:
            lines.append(f"标签：{', '.join(i['_tags'])}")
        src = i.get('realchatname') or i.get('fromusr') or ''
        if src:
            lines.append(f"来源：{src}")

        if i['type'] == 5:  # 链接
            if p.get('pagetitle'):
                lines.append(f"标题：{unescape(p['pagetitle'])}")
            if p.get('desc'):
                lines.append(f"摘要：{unescape(p['desc'])}")
            url = p.get('link') or p.get('weburl')
            if url:
                lines.append(f"链接：{url}")
        elif i['type'] == 1:  # 文本
            if p.get('desc'):
                lines.append('')
                lines.append(unescape(p['desc']))
        elif i['type'] in (3, 4, 16):  # 语音/视频
            if p.get('title'):
                lines.append(f"标题：{unescape(p['title'])}")
            lines.append('（媒体文件，未随本数据库导出）')
        elif i['type'] == 6:  # 位置
            for lc in p.get('locs', []):
                lines.append(f"位置：{lc.get('label') or lc.get('poiname') or ''} "
                             f"({lc.get('lat')},{lc.get('lng')})")
        elif i['type'] == 8:  # 文件
            if p.get('title'):
                lines.append(f"文件名：{unescape(p['title'])}")
            if p.get('desc'):
                lines.append(f"说明：{unescape(p['desc'])}")
        elif i['type'] == 14:  # 聊天记录
            if p.get('title'):
                lines.append(f"标题：{unescape(p['title'])}")
            if p.get('desc'):
                lines.append('')
                lines.append(unescape(p['desc']))
        else:
            if p.get('title') or p.get('pagetitle'):
                lines.append(f"标题：{unescape(p.get('title') or p.get('pagetitle'))}")
            if p.get('desc'):
                lines.append(f"内容：{unescape(p['desc'])}")
        lines.append('')

    os.makedirs(args.out, exist_ok=True)
    suffix = f'_{args.tag}' if args.tag else ''
    out = os.path.join(args.out, f'微信收藏{suffix}.md')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f'[+] {len(items)} 条 -> {out}')

    # 控制台摘要
    print()
    print('=== 类型分布 ===')
    for k, v in tc.most_common():
        print(f'  {k:12s} {v:4d}')
    print()
    print('=== 最近 15 条 ===')
    for i in items[:15]:
        p = i['_parsed']
        t = p.get('title') or p.get('pagetitle') or p.get('desc') or '(无标题)'
        dt = datetime.datetime.fromtimestamp(i['update_time']).strftime('%Y-%m-%d')
        print(f"  [{dt}] {i['_type_name']:8s} {unescape(t)[:60]}")


if __name__ == '__main__':
    main()
