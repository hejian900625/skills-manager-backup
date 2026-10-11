# 滴滴官网「链接排查」——渲染首页，把所有 <a> 链接和登录/订单相关文本扒出来，
# 回答：滴滴官网到底有没有「登录 / 我的订单 / 行程」入口？
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe probe_didi2.py
import re

from playwright.sync_api import sync_playwright

PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
H5_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

URLS = [
    ("滴滴升级官网", "https://www.didiglobal.com/"),
    ("滴滴出行官网", "https://www.didichuxing.com/"),
]


def probe(browser, ua, label, url, mobile=False):
    kw = {"user_agent": ua, "locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
    if mobile:
        kw.update({"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True})
    else:
        kw.update({"viewport": {"width": 1400, "height": 950}})
    ctx = browser.new_context(**kw)
    try:
        page = ctx.new_page()
        page.set_default_timeout(20000)
        try:
            page.goto(url, wait_until="networkidle", timeout=25000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        print(f"\n===== {label}  ({url})")
        print(f"  final: {page.url}")
        try:
            links = page.evaluate("""() => Array.from(document.querySelectorAll('a')).map(a => {
                const t = (a.innerText || a.textContent || '').trim().replace(/\\s+/g,' ');
                return (a.href || '') + '  ||  ' + t.slice(0, 40);
            })""")
        except Exception as e:
            links = [f"<eval err {e}>"]
        uniq = []
        for x in links:
            if x not in uniq:
                uniq.append(x)
        print(f"  链接数: {len(uniq)}")
        for x in uniq[:40]:
            print("   ", x)
        # 按钮/可点文本
        try:
            btns = page.evaluate("""() => Array.from(document.querySelectorAll('button,a,div,span'))
                .map(e => (e.innerText||'').trim().replace(/\\s+/g,' '))
                .filter(t => t && t.length < 16 && /登录|注册|我的|订单|行程|个人|中心|账|下载|客服/.test(t))""")
        except Exception:
            btns = []
        print("  命中元素:", sorted(set(btns))[:25])
    finally:
        try:
            ctx.close()
        except Exception:
            pass


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
                                    args=["--disable-blink-features=AutomationControlled"])
        for label, url in URLS:
            probe(browser, PC_UA, label + " [PC]", url, mobile=False)
            probe(browser, H5_UA, label + " [H5]", url, mobile=True)
        browser.close()


if __name__ == "__main__":
    main()
