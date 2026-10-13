# 拼多多 H5 订单导出（mobile.yangkeduo.com/orders.html）
#
# 原理（与京东同为「在页面上操作 + 监听接口响应」思路）：
#   拼多多 H5 订单页是 SSR + 接口分页，真正的结构化数据在接口里：
#     POST https://mobile.yangkeduo.com/proxy/api/api/aristotle/order_list_v4?pdduid=XXX
#     body: {"type":"all","page":N,...,"anti_content":"0as..."}   ← anti_content 是行为签名
#   我们不伪造签名，改成：**用真实浏览器滚动触发加载 → 监听响应 → 解析 orders 数组**。
#   初始一屏的数据还能从页面内嵌的 window.rawData.ordersStore.orders 直接读。
#
# 已知限制（实测结论，非 bug）：
#   ① 拼多多 H5 只有「手机号 + 短信验证码」登录，没有扫码；登录态约 7 天过期。
#   ② 订单页**没有时间范围筛选**（只有 全部/待付款/待分享/待发货/待收货/评价 状态页签），
#      也**没有导出按钮** → 能拿多少取决于列表下拉加载到多早。
#   ③ 页面 DOM 里**不显示下单时间**，但接口里 orderTime 是 Unix 时间戳（可还原到分钟）。
#
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe pdd_export.py
# 产出（数据结果/）：
#   pdd_orders_<date>.xlsx / .csv  ← 订单表
#   pdd_export.log                 ← 本次日志
#   pdd_api/raw_NN.json            ← 订单接口原始响应（备查）
#   pdd_session.json               ← 登录态（下次免短信，约 7 天有效）
import csv
import datetime as dt
import json
import os
import re
import sys
import time
import traceback

from playwright.sync_api import sync_playwright

OUT = "数据结果"                        # 登录态/日志/原始接口响应（调试产物，不进数据管线）
API_DIR = os.path.join(OUT, "pdd_api")
ORDERS_URL = "https://mobile.yangkeduo.com/orders.html"
STATE = os.path.join(OUT, "pdd_session.json")
LOG_PATH = os.path.join(OUT, "pdd_export.log")
# 订单表格落点：直接进个人站数据管线的 orders 目录，免去手动 copy（可用环境变量 ORDERS_DIR 覆盖）
ORDERS_DIR = os.environ.get("ORDERS_DIR", r"D:\site_sources\orders")

UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

LOGIN_COOKIE_HINTS = ("accesstoken", "pdd_user_id", "pdd_id", "pdd_user_uin")

ORDER_API_HINTS = ("order_list", "my_order_group", "order_list_v4")

FIELDS = ["订单号", "下单时间", "订单状态", "金额类型", "实付金额", "应付金额", "优惠金额",
          "运费", "店铺", "商品", "件数", "快递单号", "订单类型", "状态码", "来源"]

CSV_HEADER = FIELDS

# 已抓订单：orderSn -> 行 dict
ORDERS = {}
# 已抓接口响应数
REQ_COUNT = {"n": 0}
RAW_IDX = {"n": 0}
FIRST_KEYS_LOGGED = {"done": False}
# 解析失败的订单数（用于诊断）
BAD_ROWS = {"n": 0}
# 每次响应里解析出的订单条数（用于分页诊断）
PAGE_SIZES = []
# 响应处理异常计数
ERR_COUNT = {"n": 0}


# ---------------------------------------------------------------- 日志双写
class _Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for f in self.streams:
            try:
                f.write(s)
            except Exception:
                pass

    def flush(self):
        for f in self.streams:
            try:
                f.flush()
            except Exception:
                pass


# ---------------------------------------------------------------- 工具
def pump(page, ms):
    """等待并**驱动 Playwright 事件循环**（裸 time.sleep 不驱动，响应回调不会执行）。"""
    try:
        page.wait_for_timeout(ms)
    except Exception:
        time.sleep(ms / 1000.0)


def walk_orders(obj, sink):
    """递归找出所有「像订单」的 dict（含 orderSn 键）。"""
    if isinstance(obj, dict):
        if obj.get("orderSn") or obj.get("order_sn"):
            sink.append(obj)
        for v in obj.values():
            walk_orders(v, sink)
    elif isinstance(obj, list):
        for v in obj:
            walk_orders(v, sink)


def _as_dict(v):
    """接口里 price_desc / mall 等字段可能是 JSON **字符串**（首屏 rawData 里是 dict），统一成 dict。"""
    if isinstance(v, dict):
        return v
    if isinstance(v, str) and v.strip().startswith("{"):
        try:
            d = json.loads(v)
            return d if isinstance(d, dict) else {}
        except Exception:
            return {}
    return {}


def _fmt_yuan(v):
    """元值 → 两位小数字符串。"""
    if v is None or v == "":
        return ""
    s = str(v).strip()
    try:
        return f"{float(s):.2f}"
    except Exception:
        return s


def _fmt_fen(v):
    """分值 → 元字符串（/100）。"""
    if v is None or v == "":
        return ""
    s = str(v).strip()
    try:
        return f"{float(s) / 100.0:.2f}"
    except Exception:
        return s


def money(o, camel_key, snake_key):
    """金额归一成「元」。

    实测两套数据源的单位**按值类型**区分（而不是按字段名）：
      · 字符串 → 已经是「元」（如首屏 orderAmount = "16.7"）；
      · 数字   → 「分」，需 /100（如首屏 displayAmount = 1670、接口 order_amount = 164135）。
    """
    v = o.get(camel_key)
    if v in (None, ""):
        v = o.get(snake_key)
    if v in (None, ""):
        return ""
    if isinstance(v, str):
        return _fmt_yuan(v)
    return _fmt_fen(v)


def fmt_time(ts):
    try:
        ts = int(ts)
        if ts <= 0:
            return ""
        return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


def _order_time_str(o):
    """下单时间。

    普通订单有 orderTime/order_time；多多买菜订单（type=2）没有，改成
    group_order.create_at，兜底还能从 sort_id 的前 10 位（Unix 秒）还原。
    """
    for k in ("orderTime", "order_time"):
        if o.get(k):
            s = fmt_time(o.get(k))
            if s:
                return s
    go = o.get("group_order")
    if isinstance(go, dict):
        for k in ("create_at", "success_time"):
            if go.get(k):
                s = fmt_time(go.get(k))
                if s:
                    return s
    sid = o.get("sort_id")
    if isinstance(sid, str) and len(sid) >= 11 and sid[:10].isdigit():
        s = fmt_time(int(sid[:10]))
        if s:
            return s
    return ""


def _nested_goods(o):
    """商品列表：普通订单在 orderGoods/order_goods；
    多多买菜订单（type=2）把商品嵌在子数组 orders[].order_goods 里。"""
    g = o.get("orderGoods") or o.get("order_goods")
    if isinstance(g, list) and g:
        return g
    out = []
    sub = o.get("orders")
    if isinstance(sub, list):
        for s in sub:
            if isinstance(s, dict):
                g2 = s.get("orderGoods") or s.get("order_goods")
                if isinstance(g2, list):
                    out.extend(g2)
    if out:
        return out
    return g if isinstance(g, list) else []


def order_to_row(o):
    """把接口/SSR 里的一个订单对象拍平成表格行。任何异常都吞掉并返回 None（单条坏数据不该毁掉整批）。"""
    if not isinstance(o, dict):
        return None
    try:
        sn = o.get("orderSn") or o.get("order_sn") or ""
        if not sn:
            return None

        mall = _as_dict(o.get("mall"))
        shop = mall.get("mallName") or mall.get("mall_name") or ""

        goods = _nested_goods(o)
        names, specs, num = [], [], 0
        for g in goods:
            if not isinstance(g, dict):
                continue
            gn = (g.get("goodsName") or g.get("goods_name") or "").strip()
            sp = (g.get("spec") or g.get("goods_spec") or "").strip()
            try:
                n = int(g.get("goodsNumber") or g.get("goods_number") or 0)
            except Exception:
                n = 0
            num += max(n, 0)
            if gn:
                names.append(gn + (f"（{sp}）" if sp else ""))
        goods_text = " / ".join(names)
        if not num and goods:
            num = len(goods)
        if num == 0 and not goods:
            num = ""

        pd = _as_dict(o.get("priceDesc") or o.get("price_desc"))
        pd2 = _as_dict(o.get("priceDescV2") or o.get("price_desc_v2"))
        amount_kind = (pd.get("prefix") or pd2.get("prefix") or "").strip().rstrip(":：")

        # 实付 / 应付 / 优惠 / 运费（按值类型自动区分「元」和「分」两套来源）
        paid = money(o, "orderAmount", "order_amount")
        display = money(o, "displayAmount", "display_amount")
        discount = money(o, "discountAmount", "discount_amount")
        shipping = money(o, "shippingAmount", "shipping_amount")
        # 多多买菜订单没有 order_amount，只有 display_amount，
        # 且 price_desc_v2 的 prefix 明确写着「实付:」→ 把 display 视为实付。
        if not paid and display and str(pd2.get("prefix") or "").startswith("实付"):
            paid = display

        status_text = o.get("orderStatusPrompt") or o.get("order_status_prompt") or ""
        st_code = o.get("combinedOrderStatus", o.get("combined_order_status", ""))

        row = {
            "订单号": sn,
            "下单时间": _order_time_str(o),
            "订单状态": status_text,
            "金额类型": amount_kind,
            "实付金额": paid,
            "应付金额": display,
            "优惠金额": discount,
            "运费": shipping,
            "店铺": shop,
            "商品": goods_text,
            "件数": num,
            "快递单号": o.get("trackingNumber", o.get("tracking_number", "")) or "",
            "订单类型": "全部",
            "状态码": st_code,
            "来源": "拼多多H5",
        }
        # 时间仍然缺失时，用订单号前缀还原日期（如 260628-…、PO-230318-…）
        if not row["下单时间"]:
            m = re.match(r"^(?:[A-Za-z]{2}-)?(\d{2})(\d{2})(\d{2})-", sn)
            if m:
                row["下单时间"] = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return row
    except Exception as e:
        BAD_ROWS["n"] += 1
        if BAD_ROWS["n"] <= 3:
            print(f"   !! 单条订单解析失败（已跳过）: {type(e).__name__}: {e}")
        return None


def iter_order_objs(obj):
    """从一个响应/SSR 数据里取出候选订单对象列表。

    · 接口 order_list_v4 的可靠结构是**顶层 `orders` 数组**（snake_case），优先走这条；
    · 首屏 window.rawData 是嵌套的 ordersStore.orders（camelCase），用 walk 兜底。
    """
    if isinstance(obj, dict) and isinstance(obj.get("orders"), list):
        return list(obj["orders"])
    sink = []
    walk_orders(obj, sink)
    return sink


def collect_orders(obj, tag=""):
    """从接口/SSR 数据里抽订单并合并进 ORDERS。返回新增条数。"""
    sink = iter_order_objs(obj)
    PAGE_SIZES.append(len(sink))
    added = 0
    for o in sink:
        row = order_to_row(o)
        if not row:
            continue
        sn = row["订单号"]
        if sn in ORDERS:
            # 补全空字段
            for k, v in row.items():
                if v not in ("", None) and not ORDERS[sn].get(k):
                    ORDERS[sn][k] = v
            continue
        ORDERS[sn] = row
        added += 1
    return added


def has_login_cookie(ctx):
    try:
        names = {c.get("name", "").lower() for c in ctx.cookies()}
        return any(any(h in n for h in LOGIN_COOKIE_HINTS) for n in names)
    except Exception:
        return False


def do_scroll(page):
    """多策略滚动到底，触发「上拉加载更多」。"""
    try:
        box = page.viewport_size or {"width": 390, "height": 844}
        page.mouse.move(box["width"] / 2, box["height"] / 2)
        for _ in range(3):
            page.mouse.wheel(0, 2500)
            pump(page, 250)
    except Exception:
        pass
    try:
        page.evaluate("""() => {
            const els = [document.scrollingElement, document.body, document.documentElement];
            document.querySelectorAll('*').forEach(e => {
                if (e.scrollHeight > e.clientHeight + 200) els.push(e);
            });
            els.forEach(e => { try { e.scrollTop = e.scrollHeight; } catch(_){} });
            window.scrollTo(0, document.body.scrollHeight);
            window.dispatchEvent(new Event('scroll'));
        }""")
    except Exception:
        pass


def no_more_visible(page):
    try:
        return bool(page.evaluate("""() => {
            const t = document.body ? document.body.innerText : '';
            if (/没有更多/.test(t)) return true;
            const el = document.querySelector('.rbl-load-more');
            if (!el) return false;
            const cls = (el.className || '').toString();
            return cls.indexOf('pull-up-hide') === -1 &&
                   /没有更多/.test(el.innerText || '');
        }"""))
    except Exception:
        return False


# ---------------------------------------------------------------- 导出
def write_files():
    rows = sorted(ORDERS.values(), key=lambda r: (r.get("下单时间") or ""), reverse=True)
    date = dt.datetime.now().strftime("%Y-%m-%d")
    os.makedirs(ORDERS_DIR, exist_ok=True)
    base = os.path.join(ORDERS_DIR, f"pdd_orders_{date}")
    csv_path = base + ".csv"
    xlsx_path = base + ".xlsx"

    def clean(v):
        return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()

    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for r in rows:
            w.writerow([clean(r.get(k, "")) for k in CSV_HEADER])
    print(f">>> CSV 已写出: {csv_path}（{len(rows)} 行）")

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        wb = Workbook()
        ws = wb.active
        ws.title = "拼多多订单"
        ws.append(CSV_HEADER)
        for c in ws[1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="E02E24")   # 拼多多红
            c.alignment = Alignment(horizontal="center")
        for r in rows:
            ws.append([clean(r.get(k, "")) for k in CSV_HEADER])
        widths = [22, 20, 12, 14, 12, 12, 12, 8, 26, 46, 7, 20, 10, 10, 12]
        for i, wd in enumerate(widths, start=1):
            ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = wd
        ws.freeze_panes = "A2"
        wb.save(xlsx_path)
        print(f">>> Excel 已写出: {xlsx_path}")
    except Exception as e:
        print("!! 写 Excel 失败:", type(e).__name__, e)
    return rows


def summary(rows):
    print()
    print("=" * 62)
    print(f"共解析订单: {len(rows)} 条")
    if not rows:
        return
    years = {}
    status = {}
    total = 0.0
    for r in rows:
        y = (r.get("下单时间") or "")[:4] or "(无时间)"
        years[y] = years.get(y, 0) + 1
        s = r.get("订单状态") or "(无状态)"
        status[s] = status.get(s, 0) + 1
        try:
            total += float(r.get("实付金额") or 0)
        except Exception:
            pass
    order = sorted(years.items(), reverse=True)
    print("年份分布:", "  ".join(f"{k}:{v}" for k, v in order))
    print("状态分布:", "  ".join(f"{k}:{v}" for k, v in status.items()))
    print(f"实付金额合计: ¥{total:.2f}")
    ts = [r["下单时间"] for r in rows if r.get("下单时间")]
    if ts:
        print("时间跨度:", min(ts)[:10], "~", max(ts)[:10])
    print("=" * 62)


# ---------------------------------------------------------------- 主流程
def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(API_DIR, exist_ok=True)
    have_state = os.path.exists(STATE)
    print(f">>> 登录态文件: {STATE} （{'已存在，将尝试复用' if have_state else '不存在，需要登录'}）")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=["--disable-blink-features=AutomationControlled"])
        kw = {"user_agent": UA, "viewport": {"width": 390, "height": 844},
              "is_mobile": True, "has_touch": True,
              "locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
        ctx = browser.new_context(storage_state=STATE, **kw) if have_state \
            else browser.new_context(**kw)
        page = ctx.new_page()
        page.set_default_timeout(60000)

        def on_response(resp):
            try:
                u = resp.url
                if not any(h in u for h in ORDER_API_HINTS):
                    return
                if "yangkeduo.com" not in u and "pinduoduo.com" not in u:
                    return
                data = None
                try:
                    data = resp.json()
                except Exception:
                    try:
                        txt = resp.text()
                        m = re.search(r"\{.*\}", txt, re.S)
                        if m:
                            data = json.loads(m.group(0))
                    except Exception:
                        data = None
                if data is None:
                    return
                REQ_COUNT["n"] += 1
                RAW_IDX["n"] += 1
                try:
                    with open(os.path.join(API_DIR, f"raw_{RAW_IDX['n']:02d}.json"),
                              "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=1)
                except Exception:
                    pass
                if not FIRST_KEYS_LOGGED["done"] and isinstance(data, dict):
                    FIRST_KEYS_LOGGED["done"] = True
                    print(f"[API] 首次订单接口响应顶层键: {list(data.keys())[:12]}")
                n = collect_orders(data)
                total = len(ORDERS)
                page_n = PAGE_SIZES[-1] if PAGE_SIZES else 0
                print(f"[API] 捕获订单接口（第 {REQ_COUNT['n']} 次）"
                      f"本页 {page_n} 条，新增 {n}，累计 {total}")
            except Exception as e:
                ERR_COUNT["n"] += 1
                if ERR_COUNT["n"] <= 5:
                    print(f"!! 响应处理异常（第 {ERR_COUNT['n']} 次）: {type(e).__name__}: {e}")

        page.on("response", on_response)

        # ---- 打开订单页 ----
        for attempt in range(3):
            try:
                page.goto(ORDERS_URL, wait_until="domcontentloaded")
                break
            except Exception as e:
                print(f"!! goto 第 {attempt+1} 次失败: {type(e).__name__}")
                pump(page, 2000)
        pump(page, 4000)
        print(">>> 当前 URL:", page.url)

        # ---- 未登录则等短信登录 ----
        if not has_login_cookie(ctx) or "login.html" in page.url:
            print(">>> 请在窗口里用【手机号 + 短信验证码】登录拼多多（最多等 360 秒）…")
            deadline = time.time() + 360
            last = -1
            while time.time() < deadline:
                if has_login_cookie(ctx) and "login.html" not in page.url:
                    print(">>> 检测到登录成功（订单页已打开）")
                    break
                w = int(360 - (deadline - time.time()))
                if w // 10 != last:
                    last = w // 10
                    print(f"    [{w}s] 等待登录… URL={page.url[:90]}")
                pump(page, 2000)
            else:
                print("!! 超时未登录，退出")
                try:
                    browser.close()
                except Exception:
                    pass
                return
            try:
                ctx.storage_state(path=STATE)
                print(">>> 登录态已保存:", STATE)
            except Exception:
                pass
            for _ in range(3):
                try:
                    page.goto(ORDERS_URL, wait_until="domcontentloaded")
                    break
                except Exception:
                    pump(page, 2000)
            pump(page, 5000)
        else:
            print(">>> 登录态有效，免登录")
            try:
                ctx.storage_state(path=STATE)
            except Exception:
                pass

        print(">>> 已进入订单页:", page.url)

        # ---- 第一屏：从内嵌 window.rawData 直接抠 ----
        try:
            raw = page.evaluate("() => window.rawData || null")
            if raw:
                n = collect_orders(raw, "rawData")
                print(f">>> 页面内嵌 rawData：新增 {n}，累计订单 {len(ORDERS)}")
        except Exception as e:
            print("   rawData 读取失败:", type(e).__name__)
        print(f">>> 首屏累计订单: {len(ORDERS)}")

        # ---- 反复下拉加载更多 ----
        # 分页结束判定：连续 4 轮无新增，或页面出现「没有更多了」，或达到轮数上限。
        stable, rnd = 0, 0
        MAX_ROUNDS = 60
        while rnd < MAX_ROUNDS:
            rnd += 1
            before = len(ORDERS)
            req_before = REQ_COUNT["n"]
            do_scroll(page)
            pump(page, 2000)          # 必须用 wait_for_timeout 才会驱动事件循环
            after = len(ORDERS)
            req_now = REQ_COUNT["n"]
            if after > before:
                print(f"   [{rnd}] 拉到新订单 +{after-before}（累计 {after}）")
                stable = 0
            else:
                stable += 1
                if req_now == req_before:
                    hint = "（本轮未触发接口请求）"
                else:
                    hint = f"（本轮触发 {req_now - req_before} 次请求但无新订单）"
                print(f"   [{rnd}] 无新增（累计 {after}，接口请求 {req_now}）"
                      f"连续 {stable}/4 {hint}")
                if stable >= 4:
                    break
                pump(page, 1200)
            if no_more_visible(page):
                print("   页面出现「没有更多了」，停止加载")
                break
        if rnd >= MAX_ROUNDS:
            print(f"   达到轮数上限 {MAX_ROUNDS} 轮，停止加载")

        rows = write_files()
        summary(rows)
        try:
            ctx.storage_state(path=STATE)
        except Exception:
            pass
        print(">>> 完成，按回车关闭浏览器…")
        try:
            input()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass
        return rows


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    logf = open(LOG_PATH, "w", encoding="utf-8")
    sys.stdout = _Tee(sys.__stdout__, logf)
    sys.stderr = sys.stdout
    try:
        main()
    except KeyboardInterrupt:
        print("\n>>> 已中断（Ctrl+C），先把已抓到的订单落盘…")
        try:
            summary(write_files())
        except Exception:
            traceback.print_exc()
    except Exception:
        traceback.print_exc()
        try:
            summary(write_files())
        except Exception:
            pass
        try:
            input(">>> 出错了，按回车关闭…")
        except Exception:
            pass
    finally:
        try:
            print(f">>> 日志: {LOG_PATH}")
        except Exception:
            pass
        try:
            logf.close()
        except Exception:
            pass
