# 滴滴小程序「抓包取证」——mitmproxy addon
# 目的：PC 微信打开「滴滴出行」小程序 → 我的 → 订单，把滴滴域名的全部请求/响应落到磁盘，
#       回答：订单数据来自哪个接口？字段长什么样？接口要不要 wsgsig 签名？
#
# 用法（先启动本脚本，再让微信走 127.0.0.1:8899 代理）：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe -m mitmproxy \
#       --listen-port 8899 --set confdir=C:/Users/Lenovo/.mitmproxy -s mitm_didi.py
#
# 产出：C:/Users/Lenovo/数据结果/didi_capture/flow.jsonl（每行一个完整 flow）
import json
import os
import re
import time

OUT = r"C:\Users\Lenovo\数据结果\didi_capture"
os.makedirs(OUT, exist_ok=True)

# 只看滴滴系域名，其它一律放过
TARGET_HOST = re.compile(
    r"(didiglobal|xiaojukeji|udache|didistatic|diditaxi|didimobility|didifood|"
    r"didi\.co|didiinternal|kuaidadi)", re.I)
# 高价值路径（订单/行程）打星标
KEY = re.compile(r"(order|trip|journey|bill|invoice|history|list|passenger)", re.I)

FLOW_LOG = open(os.path.join(OUT, "flow.jsonl"), "a", encoding="utf-8")
HOST_STATS = {}          # 全部 host 计数 —— 用来判断「代理是否生效」「滴滴用了哪些域名」
META = {"n": 0, "total": 0}


def _dump_stats():
    try:
        with open(os.path.join(OUT, "host_stats.json"), "w", encoding="utf-8") as f:
            json.dump(dict(sorted(HOST_STATS.items(), key=lambda kv: -kv[1])),
                      f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def _hdrs(h):
    try:
        return {k: v for k, v in h.items()}
    except Exception:
        return {}


def _body(msg):
    try:
        return msg.get_text(strict=False) or ""
    except Exception:
        try:
            return repr(msg.raw_content[:50]) if msg.raw_content else ""
        except Exception:
            return ""


class Rec:
    def response(self, flow):
        try:
            host = flow.request.pretty_host
            # 1) 全量域名统计（证明代理是否真的生效）
            META["total"] += 1
            HOST_STATS[host] = HOST_STATS.get(host, 0) + 1
            _dump_stats()          # 每个请求都落盘（实时，避免 stdout 缓冲盲区）
            # 2) 只落盘滴滴系域名
            if not TARGET_HOST.search(host):
                return
            META["n"] += 1
            req, resp = flow.request, flow.response
            req_body = _body(req)
            resp_body = _body(resp)
            rec = {
                "n": META["n"],
                "time": time.strftime("%H:%M:%S"),
                "method": req.method,
                "url": req.pretty_url,
                "host": host,
                "path": req.path,
                "req_headers": _hdrs(req.headers),
                "req_body": req_body[:20000],
                "status": resp.status_code if resp else None,
                "resp_headers": _hdrs(resp.headers) if resp else {},
                "resp_body": resp_body[:300000],
            }
            FLOW_LOG.write(json.dumps(rec, ensure_ascii=False) + "\n")
            FLOW_LOG.flush()
            star = "★" if KEY.search(req.path) else " "
            print(f"[{META['n']:>3}]{star} {req.method} {rec['status']} "
                  f"{host}{req.path[:110]}  ({len(resp_body)}B)")
        except Exception as e:
            print(f"[err] {type(e).__name__}: {e}")

    def done(self):
        _dump_stats()


addons = [Rec()]
