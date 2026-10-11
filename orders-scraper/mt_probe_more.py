# 验证「美团订单是不是真的翻到底了」——复用登录态，不重新登录。
#   ① 在页面上下文里直接 fetch 下一页接口（游标=最后一页的 lastOrderTime），看还有没有数据；
#   ② 再狂滚 20 轮，看是否还会触发 getOrderList 请求。
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe "C:/Users/Lenovo/.workbuddy/skills/orders_scraper/mt_probe_more.py"
import json
import os
import re

from playwright.sync_api import sync_playwright

OUT = "数据结果"
STATE = os.path.join(OUT, "mt_session.json")
ORDER_URL = "https://i.meituan.com/mttouch/page/order"
H5_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

hits = {"n": 0}
seen = set()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(storage_state=STATE, user_agent=H5_UA,
                                  viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True,
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        page = ctx.new_page()
        page.set_default_timeout(45000)

        def on_resp(resp):
            if "getOrderList" in resp.url:
                hits["n"] += 1
                try:
                    d = resp.json()
                    ol = (d.get("data") or {}).get("orderList") or []
                    for o in ol:
                        sid = o.get("stringOrderId") or o.get("orderid")
                        if sid:
                            seen.add(str(sid))
                    cur = (d.get("data") or {}).get("lastOrderTime")
                    print(f"    [resp #{hits['n']}] 本页 {len(ol)} 条，累计去重 {len(seen)}，游标 {cur}")
                except Exception:
                    pass

        page.on("response", on_resp)
        page.goto(ORDER_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)

        st = page.evaluate("() => window.__INITIAL_STATE__ || null") or {}
        ol0 = st.get("orderList") or []
        cursor = st.get("lastOrderTime")
        print(f">>> SSR 首屏 {len(ol0)} 条，游标 lastOrderTime={cursor}")
        for o in ol0:
            sid = o.get("stringOrderId") or o.get("orderid")
            if sid:
                seen.add(str(sid))

        # ---- ① 直接用页面上下文 fetch 下一页 ----
        print("\n>>> ① 页面内 fetch 下一页（游标 = 当前最后一页游标）")
        for cur in [cursor, 1652006859]:
            if not cur:
                continue
            try:
                res = page.evaluate("""async (cursor) => {
                    const url = '/mttouch/api/order/getOrderList?lat=0&lng=0&lastOrderTime='
                        + cursor + '&status=0&shark=1&yodaReady=h5&csecplatform=4&csecversion=4.3.0';
                    const r = await fetch(url, {credentials: 'include',
                                                headers: {'accept': 'application/json'}});
                    const t = await r.text();
                    return {status: r.status, body: t.slice(0, 4000)};
                }""", cur)
                print(f"  游标 {cur} → HTTP {res['status']}")
                body = res["body"]
                try:
                    d = json.loads(body)
                    dd = d.get("data") or {}
                    print("    code:", d.get("code"), "message:", d.get("message"))
                    print("    orderList 条数:", len(dd.get("orderList") or []),
                          " lastOrderTime:", dd.get("lastOrderTime"),
                          " total:", dd.get("total"))
                    for o in (dd.get("orderList") or [])[:3]:
                        print("      ·", o.get("stringOrderId"), o.get("title"),
                              o.get("showstatus"), o.get("catename"))
                except Exception:
                    print("    非 JSON，前 300 字:", body[:300])
            except Exception as e:
                print("  fetch 失败:", type(e).__name__, e)

        # ---- ② 狂滚 20 轮 ----
        print("\n>>> ② 连续滚动 20 轮，看是否继续触发请求")
        stall = 0
        for i in range(1, 21):
            before = hits["n"]
            try:
                page.mouse.move(195, 500)
                for _ in range(4):
                    page.mouse.wheel(0, 3000)
                    page.wait_for_timeout(300)
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
            page.wait_for_timeout(3000)
            after = hits["n"]
            pos = page.evaluate("() => [Math.round(window.scrollY), document.body.scrollHeight]")
            tail = ""
            try:
                txt = page.evaluate("() => document.body.innerText || ''")
                m = re.search(r"(没有更多[^\n]*|到底了[^\n]*|加载更多)", txt)
                if m:
                    tail = " | 页面文案: " + m.group(1)[:20]
            except Exception:
                pass
            print(f"  [{i}] 请求 {before}→{after}，累计去重 {len(seen)}，scrollY/height={pos}{tail}")
            if after == before:
                stall += 1
                if stall >= 6:
                    print("  → 连续 6 轮零请求，判定已到底")
                    break
            else:
                stall = 0

        print(f"\n>>> 最终：请求 {hits['n']} 次，订单去重 {len(seen)} 条")
        print(">>> 按回车关闭…")
        try:
            input()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
