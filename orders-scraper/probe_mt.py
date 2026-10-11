# 美团订单页「可达性」探测 —— 无头、免登录，只回答一个问题：
#   美团在 PC / H5 上到底有没有「我的订单」页面？登录门槛是什么？
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe probe_mt.py
import re
import sys
import time

from playwright.sync_api import sync_playwright

PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
H5_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

PC_URLS = [
    ("美团PC门户", "https://www.meituan.com/"),
    ("美团PC-我的", "https://www.meituan.com/account/"),
    ("美团PC-订单(猜)", "https://www.meituan.com/order/"),
    ("大众点评PC", "https://www.dianping.com/"),
]

H5_URLS = [
    ("美团H5门户", "https://i.meituan.com/"),
    ("美团H5-订单(猜)", "https://i.meituan.com/order/list"),
    ("外卖H5门户", "https://h5.waimai.meituan.com/"),
    ("外卖H5-订单(猜)", "https://h5.waimai.meituan.com/waimai/mindex/orderList"),
    ("点评H5", "https://m.dianping.com/"),
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
        page.wait_for_timeout(3000)
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
        print(f"\n===== {label}")
        print(f"  url    : {url}")
        print(f"  status : {status}")
        print(f"  final  : {final}")
        print(f"  title  : {title}")
        print(f"  len    : {len(text)} 字")
        print(f"  text   : {text[:400]}")
        kw_hit = [k for k in ("登录", "我的订单", "订单", "扫码", "验证码", "下载App", "下载 App")
                  if k in text]
        print(f"  命中   : {kw_hit}")
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
