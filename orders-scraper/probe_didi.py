# 滴滴订单页「可达性」探测 —— 无头、免登录，只回答一个问题：
#   滴滴在 PC / H5 上到底有没有「我的订单」页面？登录门槛是什么？数据源在哪？
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe probe_didi.py
import re

from playwright.sync_api import sync_playwright

PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
H5_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

PC_URLS = [
    ("滴滴出行PC官网", "https://www.didichuxing.com/"),
    ("滴滴中国PC", "https://www.didi.com/"),
    ("滴滴国际官网", "https://web.didiglobal.com/"),
    ("滴滴PC-我的(猜)", "https://www.didichuxing.com/order/"),
]

H5_URLS = [
    ("滴滴公共H5", "https://common.didiglobal.com/"),
    ("滴滴H5-订单(猜1)", "https://common.didiglobal.com/bottom/orderList"),
    ("滴滴H5-订单(猜2)", "https://common.didiglobal.com/bottom/mine"),
    ("滴滴H5(猜3)", "https://common.didiglobal.com/bottom/list"),
    ("DidiGlobal-H5", "https://h5.didiglobal.com/"),
    ("didiglobal-m", "https://m.didiglobal.com/"),
    ("滴滴静态CDN", "https://dpubstatic.udache.com/"),
]


def probe(browser, ua, label, url, mobile):
    kw = {"user_agent": ua, "locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
    if mobile:
        kw.update({"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True})
    else:
        kw.update({"viewport": {"width": 1280, "height": 900}})
    ctx = browser.new_context(**kw)
    try:
        page = ctx.new_page()
        page.set_default_timeout(20000)
        status = "?"
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
            if resp:
                status = resp.status
        except Exception as e:
            status = f"ERR {type(e).__name__}"
        page.wait_for_timeout(3500)
        try:
            title = page.title()
        except Exception:
            title = "?"
        try:
            text = page.evaluate("() => document.body ? document.body.innerText : ''")
        except Exception:
            text = ""
        text = re.sub(r"\n{2,}", "\n", (text or "").strip())
        final = page.url
        html = ""
        try:
            html = page.content()
        except Exception:
            pass
        print(f"\n===== {label}")
        print(f"  url    : {url}")
        print(f"  status : {status}")
        print(f"  final  : {final}")
        print(f"  title  : {title}")
        print(f"  len    : {len(text)} 字")
        print(f"  text   : {text[:400]}")
        kw_hit = [k for k in ("登录", "我的订单", "订单", "扫码", "验证码", "下载App", "下载 App",
                              "行程", "手机号")
                  if k in text]
        print(f"  命中   : {kw_hit}")
        # 内嵌状态
        for k in ("__INITIAL_STATE__", "__NEXT_DATA__", "window.__", "orderList", "tripList"):
            if k in html:
                i = html.find(k)
                print(f"  内嵌[{k}]@{i}: {html[i:i+220]}".replace("\n", " ")[:260])
    finally:
        try:
            ctx.close()
        except Exception:
            pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--disable-blink-features=AutomationControlled"])
        print("################ PC（桌面 UA）")
        for label, url in PC_URLS:
            probe(browser, PC_UA, label, url, mobile=False)
        print("\n\n################ H5（移动 UA）")
        for label, url in H5_URLS:
            probe(browser, H5_UA, label, url, mobile=True)
        browser.close()


if __name__ == "__main__":
    main()
