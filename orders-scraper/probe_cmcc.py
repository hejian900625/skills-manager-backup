# 中国移动网上营业厅「话费/账单/详单」入口探测（只读，不登录）
# 回答：网页端有没有话费查询、月账单、通话详单？登录方式是什么？
import os
import re
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\Lenovo\数据结果\cmcc_probe"
os.makedirs(OUT, exist_ok=True)

PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
MB_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

KEY = re.compile(r"(话费|账单|详单|余额|查询|发票|充值|流量|通话|我的|账户|积分)", re.I)

TARGETS = [
    ("PC  首页",   "https://www.10086.cn", PC_UA),
    ("PC  登录",   "https://login.10086.cn", PC_UA),
    ("PC  广东",   "https://www.10086.cn/index/gd/index.html", PC_UA),
    ("H5  首页",   "https://wap.10086.cn", MB_UA),
    ("商城",       "https://shop.10086.cn", PC_UA),
]


def dump(page, name):
    try:
        page.wait_for_timeout(3000)
    except Exception:
        pass
    try:
        html = page.content()
        open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8").write(html)
    except Exception:
        html = ""
    try:
        page.screenshot(path=os.path.join(OUT, name + ".png"))
    except Exception:
        pass
    txt = page.evaluate("() => (document.body?document.body.innerText:'')")
    links = page.evaluate("""() => { const o=[];
        document.querySelectorAll('a').forEach(a=>{const t=(a.innerText||'').trim();
        if(t) o.push(t+' -> '+(a.href||''));}); return o; }""")
    hits = [l for l in links if KEY.search(l)]
    print(f"\n===== {name} =====")
    print(f"  url  : {page.url}")
    print(f"  title: {page.title()}")
    print(f"  html : {len(html)}B, 正文 {len(txt)} 字")
    print(f"  链接 : {len(links)}，命中 {len(hits)}")
    for h in hits[:25]:
        print(f"     · {h[:130]}")
    print("  正文片段: " + re.sub(r"\s+", " ", txt)[:400])


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True,
                               args=["--disable-blink-features=AutomationControlled"])
        for name, url, ua in TARGETS:
            ctx = br.new_context(user_agent=ua,
                                 viewport={"width": 390, "height": 844}
                                 if ua == MB_UA else {"width": 1440, "height": 900})
            page = ctx.new_page()
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                dump(page, re.sub(r"[^\w]+", "_", name))
            except Exception as e:
                print(f"\n===== {name} =====\n  [ERR] {type(e).__name__}: {e}")
            ctx.close()
        br.close()


if __name__ == "__main__":
    main()
