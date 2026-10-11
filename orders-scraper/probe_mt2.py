# 美团外卖 H5 订单页深挖 —— 无头、免登录，回答：
#   ① orderList 页是否要登录？② 它加载时打了哪些接口？③ 页面里有没有可直接读的结构化数据？
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe probe_mt2.py
import json
import re

from playwright.sync_api import sync_playwright

H5_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

TARGETS = [
    ("外卖订单页", "https://h5.waimai.meituan.com/waimai/mindex/orderList"),
    ("美团H5我的", "https://i.meituan.com/mttouch/page/profile"),
    ("美团H5订单中心(猜)", "https://i.meituan.com/mttouch/page/order"),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(user_agent=H5_UA, viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True,
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        page = ctx.new_page()
        page.set_default_timeout(25000)

        reqs = []
        page.on("request", lambda r: reqs.append((r.method, r.url)))

        for label, url in TARGETS:
            reqs.clear()
            print("\n" + "=" * 70)
            print(f"##### {label}  {url}")
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=25000)
                print("  status:", resp.status if resp else "?")
            except Exception as e:
                print("  goto 失败:", type(e).__name__, e)
                continue
            page.wait_for_timeout(6000)
            print("  final :", page.url)
            try:
                print("  title :", page.title())
            except Exception:
                pass
            try:
                text = page.evaluate("() => document.body ? document.body.innerText : ''")
            except Exception:
                text = ""
            text = re.sub(r"\n{2,}", "\n", (text or "").strip())
            print(f"  text({len(text)}字):", text[:350].replace("\n", " | "))
            hits = [k for k in ("登录", "验证码", "我的订单", "全部订单", "暂无订单", "待付款", "待评价")
                    if k in text]
            print("  命中关键词:", hits)
            # 页面里的全局状态变量
            try:
                gl = page.evaluate("""() => {
                    const out = [];
                    for (const k of Object.keys(window)) {
                        try {
                            const v = window[k];
                            if (v && typeof v === 'object' &&
                                (/rawData|initialState|__INITIAL|store|Store|status|data/i.test(k))) {
                                out.push(k);
                            }
                        } catch(_) {}
                    }
                    return out.slice(0, 30);
                }""")
                print("  疑似全局状态变量:", gl)
            except Exception:
                pass
            api = [u for (m, u) in reqs if re.search(r"order|api|gateway|/wm/|json", u, re.I)]
            print(f"  请求总数 {len(reqs)}，疑似接口 {len(api)} 个：")
            for u in dict.fromkeys(api):
                print("    ", u[:160])

        browser.close()


if __name__ == "__main__":
    main()
