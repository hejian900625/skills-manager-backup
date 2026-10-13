#!/usr/bin/env python3
"""微信群聊 · 基本信息导出（不含任何聊天内容）。

汇总 6 个来源：
- contact.db 的 contact 表      → 群名/备注/公告/类型
- contact.db 的 chat_room 表     → 群主
- contact.db 的 chatroom_member  → 成员数（room_id 是 contact.id，整数）
- contact.db 的 chat_room_info_detail → 群公告正文
- session.db 的 SessionTable     → 最后活跃时间/未读数/是否隐藏
- contact 表                     → 各成员真实昵称（仅用于群主显示名）

**刻意不查任何 Msg_* 表**，输出只有元数据。

用法:
  python wx_export_groups.py --out wx_export [--active-only] [--min-members N]
"""
import argparse
import collections
import datetime
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r'C:\Users\Lenovo\.workbuddy\skills\wechat-cli__skillhub\scripts')
import wcdb_key_tool_windows as W  # noqa: E402

KEYS = os.path.expanduser(r"~/.wechat-cli/all_keys.json")


def decrypt(dbdir, rel, name):
    t = tempfile.mkdtemp(prefix="wxgrp_")
    out = os.path.join(t, name)
    W._decrypt_database(os.path.join(dbdir, *rel.split("\\")), out,
                        bytes.fromhex(KEYS_MAP[rel]["enc_key"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keys', default=KEYS)
    ap.add_argument('--out', default='wx_export')
    ap.add_argument('--active-only', action='store_true',
                    help='只导出有会话记录的群（即近期活跃过的）')
    ap.add_argument('--min-members', type=int, default=0)
    args = ap.parse_args()

    global KEYS_MAP
    import json
    KEYS_MAP = json.load(open(args.keys, encoding='utf-8'))
    dbdir = KEYS_MAP['_db_dir']

    C = decrypt(dbdir, r"contact\contact.db", "c.db")
    S = decrypt(dbdir, r"session\session.db", "s.db")
    cc = sqlite3.connect(C); cc.row_factory = sqlite3.Row
    ss = sqlite3.connect(S); ss.row_factory = sqlite3.Row

    # 成员昵称表（只用于把群主 wxid 显示成人名）
    nick = {}
    for r in cc.execute("SELECT username, remark, nick_name, alias FROM contact"):
        nick[r['username']] = r['remark'] or r['nick_name'] or r['alias'] or r['username']
    nick['hejian0625'] = '我'

    # 群基础信息
    groups = {}
    for r in cc.execute("""SELECT id, username, nick_name, remark, description,
                                  chat_room_type, delete_flag, is_in_chat_room
                           FROM contact WHERE username LIKE '%@chatroom'"""):
        groups[r['username']] = dict(r)

    # 群主
    owner = {r['username']: r['owner'] for r in cc.execute("SELECT username, owner FROM chat_room")}
    rid_map = {r['username']: r['id'] for r in cc.execute("SELECT username, id FROM chat_room")}

    # 成员数
    memb = {r['room_id']: r['n'] for r in
            cc.execute("SELECT room_id, COUNT(*) AS n FROM chatroom_member GROUP BY room_id")}

    # 公告
    ann = {r['room_id_']: dict(r) for r in cc.execute(
        "SELECT room_id_, announcement_, announcement_editor_, announcement_publish_time_ "
        "FROM chat_room_info_detail")}

    # 会话元数据（不含消息内容）
    sess = {r['username']: dict(r) for r in ss.execute(
        "SELECT username, last_timestamp, unread_count, is_hidden, "
        "last_sender_display_name, type FROM SessionTable")}

    # 组装
    rows = []
    for u, g in groups.items():
        rid = rid_map.get(u, g['id'])
        s = sess.get(u) or {}
        ts = s.get('last_timestamp') or 0
        rows.append({
            'username': u,
            'name': g['nick_name'] or g['remark'] or '(未命名群)',
            'remark': g['remark'] or '',
            'type': g['chat_room_type'],
            'owner_wxid': owner.get(u, ''),
            'owner': nick.get(owner.get(u, ''), owner.get(u, '') or '—'),
            'members': memb.get(rid, 0),
            'announcement': (ann.get(rid, {}).get('announcement_') or '').strip(),
            'ann_time': ann.get(rid, {}).get('announcement_publish_time_') or 0,
            'last_ts': ts,
            'last_time': datetime.datetime.fromtimestamp(ts) if ts else None,
            'unread': s.get('unread_count') or 0,
            'hidden': s.get('is_hidden') or 0,
            'in_session': bool(s),
        })

    total = len(rows)
    if args.active_only:
        rows = [r for r in rows if r['in_session']]
    if args.min_members:
        rows = [r for r in rows if r['members'] >= args.min_members]

    # 排序：有会话的按最后活跃倒序在前，无会话的按成员数倒序在后
    active = sorted([r for r in rows if r['last_ts']], key=lambda r: -r['last_ts'])
    dormant = sorted([r for r in rows if not r['last_ts']],
                     key=lambda r: (-r['members'], r['name']))
    rows = active + dormant

    L = []
    L.append('# 微信群聊 · 基本信息')
    L.append('')
    L.append('> 本表**只含群元数据**，不含任何聊天记录内容。')
    L.append('')
    L.append(f'- 群总数（含已退出/静默群）：**{total}**')
    L.append(f'- 有会话记录（近期活跃）：**{sum(1 for r in rows if r["in_session"])}**')
    L.append(f'- 当前导出：**{len(rows)}** 个')
    L.append(f'- 导出时间：{datetime.datetime.now():%Y-%m-%d %H:%M}')
    L.append('')

    # ---- 统计 ----
    mc = collections.Counter(r['members'] for r in rows)
    buckets = collections.Counter()
    for r in rows:
        n = r['members']
        b = ('0（无成员数据）' if n == 0 else '1-5 人' if n <= 5 else
             '6-20 人' if n <= 20 else '21-50 人' if n <= 50 else
             '51-100 人' if n <= 100 else '100+ 人')
        buckets[b] += 1
    L.append('## 规模分布')
    L.append('')
    L.append('| 规模 | 群数 |')
    L.append('| --- | --- |')
    for k in ['1-5 人', '6-20 人', '21-50 人', '51-100 人', '100+ 人', '0（无成员数据）']:
        if buckets.get(k):
            L.append(f'| {k} | {buckets[k]} |')
    L.append('')

    # 活跃度分布
    now = datetime.datetime.now()
    act = collections.Counter()
    for r in rows:
        if not r['last_time']:
            act['无记录'] += 1
            continue
        d = (now - r['last_time']).days
        act['一周内' if d <= 7 else '一月内' if d <= 30 else
            '三月内' if d <= 90 else '一年内' if d <= 365 else '一年以上'] += 1
    L.append('## 活跃度分布（按会话最后消息时间）')
    L.append('')
    L.append('| 最后活跃 | 群数 |')
    L.append('| --- | --- |')
    for k in ['一周内', '一月内', '三月内', '一年内', '一年以上', '无记录']:
        if act.get(k):
            L.append(f'| {k} | {act[k]} |')
    L.append('')

    # 群主 TOP
    oc = collections.Counter(r['owner'] for r in rows if r['owner'] and r['owner'] != '—')
    L.append('## 群主 TOP 20（按名下群数）')
    L.append('')
    L.append('| 群主 | 群数 |')
    L.append('| --- | --- |')
    for k, v in oc.most_common(20):
        L.append(f'| {k} | {v} |')
    L.append('')

    # ---- 明细表 ----
    L.append('## 群列表（按最后活跃倒序，无记录者按人数倒序）')
    L.append('')
    L.append('| # | 群名 | 成员 | 群主 | 最后活跃 | 未读 | 群ID |')
    L.append('| --- | --- | --- | --- | --- | --- | --- |')
    for n, r in enumerate(rows, 1):
        nm = r['name'].replace('|', '\\|')
        lt = r['last_time'].strftime('%Y-%m-%d') if r['last_time'] else '—'
        L.append(f"| {n} | {nm} | {r['members']} | {r['owner']} | {lt} | "
                 f"{r['unread'] or ''} | `{r['username']}` |")
    L.append('')

    # ---- 有公告的群 ----
    withann = [r for r in rows if r['announcement']]
    if withann:
        L.append('---')
        L.append('')
        L.append(f'## 群公告摘录（{len(withann)} 个群有公告）')
        L.append('')
        for r in withann[:60]:
            txt = r['announcement'].replace('\n', ' ')[:200]
            L.append(f"**{r['name']}**（{r['members']} 人）")
            L.append('')
            L.append(f'> {txt}')
            L.append('')

    os.makedirs(args.out, exist_ok=True)
    dst = os.path.join(args.out, '微信群聊_基本信息.md')
    txt = '\n'.join(L)
    open(dst, 'w', encoding='utf-8').write(txt)
    print(f'[OK] {len(rows)}/{total} 个群 -> {dst}')
    print(f'     {len(txt.splitlines())} 行, {len(txt)/1024:.0f} KB')
    print(f'活跃(有会话): {sum(1 for r in rows if r["in_session"])}')
    print(f'有公告: {sum(1 for r in rows if r["announcement"])}')
    print('规模:', dict(buckets.most_common()))
    print('活跃:', dict(act))
    print('群主TOP5:', oc.most_common(5))


if __name__ == '__main__':
    main()