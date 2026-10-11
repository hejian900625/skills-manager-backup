# 京东订单导出 v8（遍历时间范围 + 确定性翻页补齐）
# 由 orders_scraper/jd.py 重写。新版京东订单页是 React SPA：
#   - 无导出按钮、无传统分页链接
#   - 默认只显示「近3个月订单」，页面有时间下拉：近3个月/今年内/2025/.../2014/2014前
#   - 订单数据来自 JSON 接口（带 h5st 签名，不能伪造参数直连）
#   - 单个时间范围**每次只返回 20 条**（服务端 totalNum 可能远大于 20）
#     → 必须点「下一页」触发 page=2,3... 的后续请求
#
# 原理（完全避开签名难题）：
#   1) 打开订单页 → 监听所有响应，识别含 data.orderList 的订单接口，解析结构化订单
#   2) 用真实鼠标点击「时间下拉」→ 逐个点击每个年份选项 → 页面自己带签名请求
#   3) 每个范围内：**按 totalNum 判定是否需要翻页** → 点「下一页」→ 等新响应 → 循环
#   4) 汇总去重 → 写 Excel + CSV（字段干净，无换行）
#   5) 记录每次切换对应的接口参数（含 page）到 数据结果/jd_api/_urls.txt
#
# v8 关键修复（相对 v7）：
#   ★ pump()：用 page.wait_for_timeout 代替裸 time.sleep —— 后者**不会驱动 Playwright
#     事件循环**，导致 page.on("response") 回调迟迟不执行（v6 误判根源）。
#   ★ 下拉：先判断是否已展开，已展开就直接读，**不再"再点一下又关掉"**。
#   ★ 翻页：用接口返回的 totalNum 决定是否/何时停止，不再对无关元素瞎等超时。
#   ★ 翻页控件只认「下一页 / 加载更多」，去掉会误匹配的「查看更多」。
#   ★ Ctrl+C 不再丢数据：中断后照样把已抓到的订单写成表格。
#
# 产出（数据结果/）：
#   jd_orders_<date>.xlsx / .csv
#   jd_export.log            本次完整日志（stdout 同步落盘）
#   jd_api/_urls.txt         接口地址与参数（含时间选项 + page 映射）
#   jd_api/raw_*.json        原始订单接口响应
import os
import re
import json
import time
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = "https://order.jd.com/center/list.action"
OUT_DIR = "数据结果"
API_DIR = os.path.join(OUT_DIR, "jd_api")
STATE = os.path.join(OUT_DIR, "jd_session.json")  # 登录态持久化

AUTH_COOKIE_NAMES = ("pt_key", "pin")   # PC 端登录用 pin（pt_key 是手机端）
LOGIN_MARKERS = ["text=订单中心", "text=我的订单", "#orderLite", "[class*='orderCard-']"]

SEL_SELECT_CONTAINER = '[class*="selectContainer-"]'
SEL_SELECT_LIST = '[class*="selectList-"]'
SEL_OPTION = '[class*="selectList-"] [class*="item-"]'

# 翻页控件文本（「下一页」优先）。**不要加「查看更多」**：页面上别处也有这个词，会误点/瞎等。
PAGER_LABELS = ("下一页", "加载更多")

ORDER_API_HOST = "api.m.jd.com"
ORDER_API_FN = "pcorder_center_list"
PAGE_SIZE = 20


# ----------------------------------------------------------------------------- helpers

def pump(page, ms):
    """等待 ms 毫秒，**同时驱动 Playwright 事件循环**。

    这是 v8 的关键修复：裸 `time.sleep()` 只会让主线程睡着，Playwright 的
    `page.on("response", ...)` 回调挂在它自己的事件循环上，**不会被调度**，
    于是"点了按钮却看不到新请求"，此前多轮误判都源于此。
    `page.wait_for_timeout()` 是 Playwright 调用，会正常泵动事件循环。
    """
    try:
        page.wait_for_timeout(ms)
    except Exception:
        time.sleep(ms / 1000.0)


def extract_json(text):
    """从（可能的）jsonp 包装里取出 JSON 对象。"""
    if not text:
        return None
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    if i == -1 or j == -1 or j <= i:
        return None
    try:
        return json.loads(s[i:j + 1])
    except Exception:
        return None


def clean(x):
    if x is None:
        return ""
    return re.sub(r"\s+", " ", str(x)).strip()


def count_cards(page):
    try:
        return page.eval_on_selector_all("[class*='orderCard-']", "e=>e.length")
    except Exception:
        return -1


def scroll_to_bottom(page):
    """多次滚动到底，确保列表底部/「下一页」进入可点区域。"""
    try:
        page.mouse.move(600, 400)
        for _ in range(3):
            page.mouse.wheel(0, 6000)
            pump(page, 320)
    except Exception:
        pass
    try:
        page.evaluate("""() => {
            document.querySelectorAll('*').forEach(e => {
                if (e.scrollHeight > e.clientHeight + 40 && e.clientHeight > 100)
                    e.scrollTop = e.scrollHeight;
            });
            if (document.scrollingElement)
                document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight;
            window.scrollTo(0, document.body.scrollHeight);
        }""")
    except Exception:
        pass
    pump(page, 500)


def drop_tooltip_banner(page):
    """移除"下载京东桌面版"那条推广横幅，避免遮挡下拉/翻页控件。"""
    try:
        page.evaluate("""() => {
            document.querySelectorAll('[class*="tooltipFilter-"]').forEach(e => e.remove());
        }""")
    except Exception:
        pass


# ----------------------------------------------------------------------------- 登录

def has_login_cookie(context):
    """京东登录成功的判据：Cookie 里有 pt_key（手机端）或 pin（PC 端）。"""
    try:
        names = {c.get("name") for c in context.cookies()}
        for n in AUTH_COOKIE_NAMES:
            if n in names:
                return True
    except Exception:
        pass
    return False


def ensure_logged_in(context, page, timeout_s=300):
    """等登录：以 pt_key/pin Cookie 为准（扫码后页面常停在 passport 不自动跳）。
    登录成功后**显式**跳回订单页，确保订单接口被触发。"""
    print(f">>> 请扫码登录京东（最多等 {timeout_s} 秒；已登录会立即通过）…")
    deadline = time.time() + timeout_s
    waited = 0
    last_report = -1
    while time.time() < deadline:
        if has_login_cookie(context):
            print(">>> 检测到登录成功（pt_key/pin Cookie 已写入）")
            break
        if waited // 5 != last_report:
            last_report = waited // 5
            try:
                url = page.url
            except Exception:
                url = "(取不到)"
            try:
                n_ok = len(context.cookies())
            except Exception:
                n_ok = -1
            login_page = ("passport.jd.com" in url) or ("login" in url.lower())
            print(f"    [{waited}s] URL={url[:90]}")
            print(f"          cookie数={n_ok}  登录页={'是（请扫码）' if login_page else '否'}")
        try:
            if "passport.jd.com" not in page.url and "login" not in page.url.lower():
                for m in LOGIN_MARKERS:
                    if page.query_selector(m):
                        print(">>> 检测到已进入订单页")
                        return True
        except Exception:
            pass
        pump(page, 2000)
        waited += 2
    else:
        print("!! 超时未检测到登录（pt_key/pin 未出现）")
        return False

    print(">>> 显式跳转到订单页…")
    for attempt in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(f"!! 跳转第 {attempt+1} 次失败: {type(e).__name__}: {str(e)[:100]}")
            pump(page, 2000)
    pump(page, 4000)
    print(">>> 当前 URL:", page.url)
    return True


# ----------------------------------------------------------------------------- 时间下拉

def dropdown_is_open(page):
    """时间下拉面板是否已展开（selectList 只在展开时才存在/可见）。"""
    try:
        return page.evaluate("""() => {
            const el = document.querySelector('%s');
            if (!el) return false;
            const r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0;
        }""" % SEL_SELECT_LIST)
    except Exception:
        return False


def read_time_options(page, rounds=8):
    """读出时间下拉的**全部**选项：下拉列表本身可滚动，只读可视区会漏掉 2015/2014/2014前。"""
    try:
        page.evaluate("""() => { const el = document.querySelector('%s');
                                  if (el) el.scrollTop = 0; }""" % SEL_SELECT_LIST)
    except Exception:
        pass
    seen = []
    for _ in range(rounds):
        try:
            vals = page.eval_on_selector_all(
                SEL_OPTION, "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean)")
        except Exception:
            vals = []
        for v in vals:
            if v not in seen:
                seen.append(v)
        try:
            moved = page.evaluate("""() => {
                const el = document.querySelector('%s');
                if (!el) return false;
                const before = el.scrollTop;
                el.scrollTop = Math.min(el.scrollTop + el.clientHeight * 0.8, el.scrollHeight);
                return el.scrollTop > before;
            }""" % SEL_SELECT_LIST)
        except Exception:
            moved = False
        pump(page, 400)
        if not moved:
            break
    return seen


def open_time_dropdown(page):
    """展开时间下拉并返回全部选项文本。

    ★ 若已展开就**直接读**——否则再点一下容器中心会把它**关掉**（v7 的 bug：
       于是"近3个月订单"那一轮总是报"下拉展开失败"）。
    """
    if not dropdown_is_open(page):
        try:
            el = page.query_selector(SEL_SELECT_CONTAINER)
            if el:
                box = el.bounding_box()
                if box and box["width"] > 0:
                    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                    pump(page, 1200)
        except Exception as e:
            print("   展开下拉异常:", type(e).__name__, str(e)[:80])
    if not dropdown_is_open(page):
        return []
    return read_time_options(page)


def current_range_text(page):
    """当前时间下拉显示的文本（如"近3个月订单"）。"""
    try:
        return page.evaluate("""() => {
            const el = document.querySelector('%s [class*="text-"]');
            return el ? (el.innerText || '').trim() : '';
        }""" % SEL_SELECT_CONTAINER)
    except Exception:
        return ""


def click_time_option(page, text):
    """点某个时间选项（先 scrollIntoView，再真实鼠标点击）。"""
    try:
        pos = page.evaluate("""(t) => {
            const els = document.querySelectorAll('%s');
            for (const e of els) {
                if ((e.innerText || '').trim() === t) {
                    e.scrollIntoView({block: 'center'});
                    const r = e.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return null;
        }""" % SEL_OPTION, text)
        if not pos:
            return False
        page.mouse.click(pos["x"], pos["y"])
        return True
    except Exception as e:
        print("   点击选项异常:", type(e).__name__, str(e)[:80])
        return False


# ----------------------------------------------------------------------------- 翻页

def wait_new_requests(page, req_count, n0, timeout_ms=20000, tick=300):
    """轮询等待"订单接口请求数"增加。用 pump() 保证响应回调能被调度。"""
    deadline = time.time() + timeout_ms / 1000.0
    while time.time() < deadline:
        pump(page, tick)
        if req_count() > n0:
            return True
    return False


def find_pager(page):
    """找翻页控件（「下一页」优先）。返回 {'label','nth','x','y'} 或 None。"""
    for label in PAGER_LABELS:
        try:
            loc = page.locator('text="%s"' % label)
            cnt = min(loc.count(), 5)
        except Exception:
            cnt = 0
        for i in range(cnt):
            try:
                b = loc.nth(i).bounding_box()
            except Exception:
                b = None
            if b and b.get("width", 0) > 1 and b.get("height", 0) > 1:
                return {"label": label, "nth": i,
                        "x": b["x"] + b["width"] / 2, "y": b["y"] + b["height"] / 2}
    return None


def click_pager(page, pager, req_count, timeout_ms=15000):
    """点翻页控件并等待新的订单接口响应。返回 True = 确实拉到新页。"""
    n0 = req_count()
    n1 = n0
    try:
        loc = page.locator('text="%s"' % pager["label"]).nth(pager["nth"])
        loc.scroll_into_view_if_needed(timeout=3000)
        loc.click(timeout=5000)
        n1 = req_count()
    except Exception as e:
        print(f"      定位器点击失败({type(e).__name__})，改用鼠标坐标兜底")
        try:
            b = page.locator('text="%s"' % pager["label"]).nth(pager["nth"]).bounding_box()
            if b:
                page.mouse.click(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2)
                n1 = req_count()
        except Exception:
            return False
    if n1 > n0:
        return True
    ok = wait_new_requests(page, req_count, n0, timeout_ms=timeout_ms)
    if not ok:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    return ok


def paginate_range(page, req_count, rng, range_stats, max_pages=30):
    """在某时间范围内按 totalNum 判定并反复点「下一页」，直到取全或没有控件。"""
    hits = 0
    for i in range(max_pages):
        st = range_stats.get(rng) or {}
        total, items = st.get("total"), st.get("items", 0)
        if total is not None and items >= total:
            print(f"   已取全 {items}/{total}，无需翻页")
            break
        drop_tooltip_banner(page)
        scroll_to_bottom(page)
        pager = find_pager(page)
        if not pager:
            print(f"   未发现翻页控件 → 本范围到底（已取 {items}/"
                  f"{total if total is not None else '?'}）")
            break
        if not click_pager(page, pager, req_count):
            print(f"   点「{pager['label']}」未拉到新页 → 本范围结束")
            break
        hits += 1
        st = range_stats.get(rng) or {}
        print(f"   [{i+1}] ✅ 点「{pager['label']}」拉到新页"
              f"（已取 {st.get('items')}/{st.get('total')}，累计订单见上）")
    return hits


# ----------------------------------------------------------------------------- 解析 / 输出

def order_to_row(o, time_range=""):
    pay = o.get("itemPayInfo") or {}
    status = (o.get("statusInfo") or {})
    shop = (o.get("shopInfo") or {})
    cons = (o.get("consigneeInfo") or {})
    wares = o.get("wareList") or []
    goods = " | ".join(clean(w.get("name")) for w in wares if w.get("name"))
    nums = sum(int(w.get("num") or 0) for w in wares)
    return {
        "订单号": clean(o.get("orderId")),
        "下单时间": clean(o.get("dateSubmit")),
        "状态": clean(status.get("orderStateName")),
        "实付金额": clean(pay.get("shouldPay") if pay.get("shouldPay") is not None else pay.get("fistPrice")),
        "订单原价": clean(pay.get("totalPrice")),
        "支付方式": clean(pay.get("paymentTypeName")),
        "配送方式": clean(o.get("shipmentTypeName")),
        "店铺": clean(shop.get("shopName")),
        "商品": goods,
        "件数": nums,
        "收货人": clean(cons.get("customerName")),
        "收货地址": clean(cons.get("address")),
        "来源范围": time_range,
    }


class _Tee:
    """同时写控制台和日志文件，便于事后排查（用户不必手动复制控制台）。"""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s)
                st.flush()
            except Exception:
                pass

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def install_log_tee():
    import sys
    log_path = os.path.join(OUT_DIR, "jd_export.log")
    try:
        f = open(log_path, "w", encoding="utf-8", errors="replace")
    except Exception:
        return None, None
    old = sys.stdout
    sys.stdout = _Tee(old, f)
    print(f">>> 日志同时写入: {log_path}")
    return old, f


# ----------------------------------------------------------------------------- main

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(API_DIR, exist_ok=True)
    install_log_tee()

    orders = {}          # orderId -> order dict（去重，跨范围合并）
    order_range = {}     # orderId -> 来源时间范围
    api_meta = []        # 接口地址与参数
    range_stats = {}     # range -> {"items": 已收条数, "total": totalNum, "resp": 响应次数}
    raw_n = {"i": 0}
    current = {"range": "近3个月订单(默认)"}

    def req_count():
        return len(api_meta)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        have_state = os.path.exists(STATE)
        context = browser.new_context(storage_state=STATE) if have_state else browser.new_context()
        page = context.new_page()
        page.set_default_timeout(30000)

        def on_response(resp):
            try:
                u = resp.url
                if ORDER_API_HOST not in u or ORDER_API_FN not in u:
                    return
                ct = resp.headers.get("content-type", "")
                if "json" not in ct and "javascript" not in ct:
                    return
                body = resp.text()
                j = extract_json(body)
                if not isinstance(j, dict):
                    return
                d = j.get("data")
                ol = d.get("orderList") if isinstance(d, dict) else None
                if not ol:
                    return
                try:
                    post = resp.request.post_data
                except Exception:
                    post = None
                api_meta.append({"url": u, "method": resp.request.method, "postData": post,
                                 "totalNum": d.get("totalNum"), "timeRange": current["range"]})
                st = range_stats.setdefault(current["range"], {"items": 0, "total": None, "resp": 0})
                st["resp"] += 1
                st["items"] += len(ol)
                st["total"] = d.get("totalNum")
                raw_n["i"] += 1
                with open(os.path.join(API_DIR, f"raw_{raw_n['i']:02d}.json"), "w",
                          encoding="utf-8") as f:
                    json.dump(j, f, ensure_ascii=False, indent=1)
                new = 0
                for o in ol:
                    oid = o.get("orderId")
                    if oid and oid not in orders:
                        orders[oid] = o
                        order_range[oid] = current["range"]
                        new += 1
                print(f"  [API] 捕获订单接口（{current['range']}）返回 {len(ol)} 条，新增 {new}，"
                      f"累计订单 {len(orders)}（该范围 totalNum={d.get('totalNum')}）")
            except Exception:
                pass

        page.on("response", on_response)

        def new_page():
            pg = context.new_page()
            pg.set_default_timeout(30000)
            pg.on("response", on_response)
            return pg

        try:
            page.goto(URL, wait_until="domcontentloaded")
        except Exception as e:
            print("!! open order page failed:", type(e).__name__, str(e)[:100])

        logged = ensure_logged_in(context, page, 300)
        if not logged and have_state:
            print(">>> 旧登录态已失效，重新登录…")
            try:
                context.close()
            except Exception:
                pass
            context = browser.new_context()
            page = new_page()
            try:
                page.goto(URL, wait_until="domcontentloaded")
            except Exception:
                pass
            logged = ensure_logged_in(context, page, 300)
        if not logged:
            print("!! 登录未完成或页面异常，退出。")
            try:
                context.close(); browser.close()
            except Exception:
                pass
            return
        try:
            context.storage_state(path=STATE)
            print(">>> 登录态已保存:", STATE)
        except Exception:
            pass
        print(">>> 已进入订单页")
        pump(page, 3000)
        drop_tooltip_banner(page)
        pump(page, 1000)

        # ---- 遍历时间范围（Ctrl+C 也保留已抓到的数据）----
        try:
            opts = open_time_dropdown(page)
            print(">>> 时间下拉选项:", opts)
            if not opts:
                print("!! 未能展开时间下拉（将只保留默认近3个月订单）")
                paginate_range(page, req_count, current["range"], range_stats)
            else:
                for opt in opts:
                    current["range"] = opt
                    cur = current_range_text(page)
                    print(f"\n>>> 切换时间范围: {opt}"
                          + ("（已是当前选中项）" if opt == cur else ""))
                    already = (opt == cur) and (range_stats.get(opt, {}).get("items", 0) > 0)
                    if already:
                        # 默认加载时已抓过，直接看是否需要翻页补齐
                        print("   已是当前选中范围且数据已抓到，检查是否需要翻页")
                        paginate_range(page, req_count, opt, range_stats)
                        continue
                    listed = open_time_dropdown(page)
                    if not listed:
                        print("   下拉展开失败，跳过")
                        continue
                    if opt not in listed:
                        print("   未在选项列表中找到该选项，跳过")
                        continue
                    n0 = req_count()
                    if not click_time_option(page, opt):
                        print("   点击选项失败，跳过")
                        continue
                    if not wait_new_requests(page, req_count, n0, timeout_ms=20000):
                        print("   （未等到新接口响应，仍尝试翻页）")
                    else:
                        print("   ✅ 已切换到该范围并拿到第 1 页数据")
                    paginate_range(page, req_count, opt, range_stats)
        except KeyboardInterrupt:
            print("\n>>> 收到 Ctrl+C：停止抓取，保存已获取的数据…")

        # ---- 写文件 ----
        with open(os.path.join(API_DIR, "_urls.txt"), "w", encoding="utf-8") as f:
            for m in api_meta:
                f.write(f"[{m['method']}] {m['url']}\n  postData: {m['postData']}\n"
                        f"  totalNum: {m['totalNum']}\n  timeRange: {m['timeRange']}\n\n")

        rows = [order_to_row(o, order_range.get(oid, "")) for oid, o in orders.items()]
        rows.sort(key=lambda r: r["下单时间"], reverse=True)
        print(f"\n>>> 共解析订单: {len(rows)} 条")
        print(">>> 各时间范围抓取情况:")
        for rng, st in range_stats.items():
            ok = "" if st["total"] is None or st["items"] >= st["total"] else "  ← 仍有缺口"
            print(f"    {rng}: {st['items']}/{st['total']}（{st['resp']} 次请求）{ok}")

        stamp = datetime.now().strftime("%Y-%m-%d")
        csv_path = os.path.join(OUT_DIR, f"jd_orders_{stamp}.csv")
        xlsx_path = os.path.join(OUT_DIR, f"jd_orders_{stamp}.xlsx")

        import csv
        fields = ["订单号", "下单时间", "状态", "实付金额", "订单原价", "支付方式",
                  "配送方式", "店铺", "商品", "件数", "收货人", "收货地址", "来源范围"]
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(">>> 已写 CSV:", csv_path)
        try:
            import pandas as pd
            pd.DataFrame(rows, columns=fields).to_excel(xlsx_path, index=False)
            print(">>> 已写 Excel:", xlsx_path)
        except Exception as e:
            print("!! 写 Excel 失败（CSV 已保存）:", e)

        print(">>> 完成。按回车关闭浏览器…")
        try:
            input()
        except Exception:
            pass
        try:
            context.close(); browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n>>> 已中断（Ctrl+C）。")
    except Exception:
        traceback.print_exc()
        try:
            input(">>> 出错了，按回车关闭…")
        except Exception:
            pass
