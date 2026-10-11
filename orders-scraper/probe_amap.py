# 高德（Amap）订单/轨迹入口探测（只读，不登录）
# 回答两个问题：
#   A. 高德打车的行程订单，网页端有没有「订单中心」？
#   B. 高德的位置轨迹（足迹/导航记录），网页端能不能拿到？
# 产出：stdout 摘要 + 数据结果/amap_probe/*.html
import os
import re
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\Lenovo\数据结果\amap_probe"
os.makedirs(OUT, exist_ok=True)

PC_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
MB_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1")

KEY = re.compile(r"(订单|行程|打车|足迹|轨迹|我的|发票|钱包|历史|记录)", re.I)

TARGETS = [
    ("PC  首页",      "https://www.amap.com", PC_UA),
    ("PC  足迹",      "https://www.amap.com/myfoot", PC_UA),
    ("PC  登录",      "https://login.amap.com", PC_UA),
    ("H5  首页",      "https://m.amap.com", MB_UA),
    ("H5  打车",      "https://m.amap.com/taxi", MB_UA),
    ("开放平台",      "https://lbs.amap.com/api/track/lieying-vedio/summary", PC_UA),
]


def snapshot(page, name):
    try:
        page.wait_for_timeout(2500)
    except Exception:
        pass
    html = ""
    try:
        html = page.content()
        with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as f:
            f.write(html)
    except Exception:
        pass
    title = ""
    try:
        title = page.title()
    except Exception:
        pass
    text = ""
    try:
        text = page.evaluate("() => (document.body ? document.body.innerText : '')")
    except Exception:
        pass
    links = []
    try:
        links = page.evaluate("""() => {
            const out = [];
            document.querySelectorAll('a').forEach(a => {
                const t = (a.innerText || '').trim();
                if (t) out.push(t + ' -> ' + (a.href || ''));
            });
            return out;
        }""")
    except Exception:
        pass
    hits = [l for l in links if KEY.search(l)]
    # 内嵌数据
    embed = []
    for k in ("__INITIAL_STATE__", "window.__NUXT__", "__NEXT_DATA__",
              "window.__INITIAL", "rawData"):
        if k in html:
            embed.append(k)
    print(f"\n===== {name} =====")
    print(f"  url   : {page.url}")
    print(f"  title : {title}")
    print(f"  html  : {len(html)}B, 正文 {len(text)} 字")
    print(f"  内嵌  : {embed or '无'}")
    print(f"  链接  : {len(links)} 个，命中关键词 {len(hits)} 个")
    for h in hits[:18]:
        print(f"     · {h[:120]}")
    if text:
        head = re.sub(r"\s+", " ", text)[:400]
        print(f"  正文  : {head}")
    return html


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True,
                               args=["--disable-blink-features=AutomationControlled"])
        for name, url, ua in TARGETS:
            ctx = br.new_context(user_agent=ua,
                                 viewport={"width": 420, "height": 900}
                                 if ua == MB_UA else {"width": 1440, "height": 900})
            page = ctx.new_page()
            try:
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                snapshot(page, re.sub(r"[^\w]+", "_", name))
            except Exception as e:
                print(f"\n===== {name} =====\n  [ERR] {type(e).__name__}: {e}")
            ctx.close()
        br.close()


if __name__ == "__main__":
    main()
