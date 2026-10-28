# -*- coding: utf-8 -*-
"""导出/导入的本地状态：记住「微信会话 → 上次导出时间 → ChatLab 会话 ID」。

用途:
  1. export_to_chatlab.py 按日期命名产物，并据此算出「相比上次导出新增了多少条」；
  2. import_chatlab.py 靠它把同一会话的后续导入精确落到原有 ChatLab 会话上（增量合并），
     不依赖会话名匹配，改过名/重名也不会错配。

状态文件都在 ~/.chatlab/ 下:
  _wx_export_state.json  {chat_id: {"date","lastMessageTs","count","file","name"}}
  _wx_import_map.json    {chat_id: {"sessionId","name","lastImportDate","lastCount"}}

全程本地，纯记录，删掉只会退化成「按会话名匹配」，不影响已有数据。
"""
import json
import os
import datetime

STATE_DIR = os.path.join(os.path.expanduser("~"), ".chatlab")
EXPORT_STATE = os.path.join(STATE_DIR, "_wx_export_state.json")
IMPORT_MAP = os.path.join(STATE_DIR, "_wx_import_map.json")


# ---------------------------------------------------------------- 基础读写

def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except Exception as e:
        print("[!] 写状态文件失败（不影响本次导入）:", e)


def today():
    """本地日期 YYYY-MM-DD。"""
    return datetime.date.today().strftime("%Y-%m-%d")


def safe_name(s):
    """把会话名变成合法文件名（Windows 禁用字符 + 结尾点空格）。"""
    s = str(s or "").strip()
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, "_")
    s = s.strip().rstrip(". ")
    return s or "chat"


def default_export_name(chat_name):
    """<会话名>_chatlab_<当天日期>.json —— 同一天重复导出会覆盖当天那份。"""
    return "%s_chatlab_%s.json" % (safe_name(chat_name), today())


# ---------------------------------------------------------------- 导出侧

def get_export_state(chat_id):
    return _load(EXPORT_STATE).get(str(chat_id)) or {}


def record_export(chat_id, chat_name, count, last_ts, path):
    data = _load(EXPORT_STATE)
    data[str(chat_id)] = {
        "name": chat_name,
        "date": today(),
        "count": count,
        "lastMessageTs": int(last_ts or 0),
        "file": os.path.abspath(path) if path else "",
        "updatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save(EXPORT_STATE, data)


def delta_summary(chat_id, messages):
    """对比上次导出，返回 (新增条数 or None, 上次日期)。None 表示没有上次记录。"""
    prev = get_export_state(chat_id)
    if not prev:
        return None, None
    last_ts = int(prev.get("lastMessageTs") or 0)
    newc = sum(1 for m in messages if int(m.get("createTime") or 0) > last_ts)
    return newc, prev.get("date")


# ---------------------------------------------------------------- 导入侧

def get_session_record(chat_id):
    return _load(IMPORT_MAP).get(str(chat_id)) or {}


def record_session(chat_id, session_id, chat_name, count, incremental):
    if not chat_id or not session_id:
        return
    data = _load(IMPORT_MAP)
    old = data.get(str(chat_id)) or {}
    data[str(chat_id)] = {
        "sessionId": session_id,
        "name": chat_name,
        "lastImportDate": today(),
        "lastCount": count,
        # 累计导入次数，方便判断是首次建会话还是后续增量
        "imports": int(old.get("imports") or 0) + 1,
        "lastMode": "incremental" if incremental else "created",
        "updatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save(IMPORT_MAP, data)
