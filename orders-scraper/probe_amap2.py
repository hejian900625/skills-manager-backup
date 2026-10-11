# 高德二次取证：登录态下挖「我的订单/打车/足迹」入口
# 第一次取证的盲区：登录后首页只 dump 了静态链接，头像下拉菜单没展开。
# 这次：复用 amap_session.json → 点开右上角头像 → 展开菜单项全量 dump → 逐个候选 URL 试。
import json
import os
import re
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\Lenovo\数据结果\amap_probe"
API = r"C:\Users\Lenovo\数据结果\amap_api2"
SESSION = r"C:\Users\Lenovo\数据结果\amap_session.json"
os.makedirs(OUT, exist_ok=True)
os.makedirs(API, exist_ok=True)

HOME = "https://www.amap.com/"
CAND = [
    "https://taxi.amap.com",
    "https://www.amap.com/service/taxi",
    "https://www.amap.com/myfoot",
    "https://www.amap.com/footprint",
    "https://www.amap.com/order",
    "https://www.amap.com/myorder",
    "https://www.amap.com/service/order",
    "https://www.amap.com/member",
    "https://www.amap.com/personal",
]
KEY = re.compile(r"(订单|行程|足迹|轨迹|打车|出行|收藏|发票|钱包|个人中心|我的)", re.I)
AVATAR_SEL = [
    "[class*='avatar']", "[class*='Avatar']", ".user-info", "[class*='userinfo']",
    "[class*='header-user']", "[class*='login-info']", "header img",
]
captured = []


def on_resp(resp):
    try:
        u = resp.url
        if not re.search(r"(order|trip|foot|track|journey|history|taxi|drive|user|member)", u, re.I):
            return
        body = ""
        try:
            ct = (resp.headers or {}).get("content-type", "")
            if "json" in ct:
                body = resp.text()[:200000]
        except Exception:
            pass
        captured.append((resp.status, u, len(body)))
        if body:
            with open(os.path.join(API, f"c_{len(captured):02d}.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"url": u, "status": resp.status, "body": body}, f,
                          ensure_ascii=False)
        print(f"  [API {len(captured):>2}] {resp.status} {u[:120]} ({len(body)}B)")
    except Exception:
        pass


def texts(page):
    try:
        return page.evaluate("""() => { const o=[];
            document.querySelectorAll('a,button,li,span,div').forEach(e=>{
              const t=(e.innerText||'').trim();
              if(t && t.length<30) o.push(t+' | '+(e.getAttribute('href')||''));});
            return [...new Set(o)]; }""")
    except Exception:
        return []


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1440, "height": 900},
            storage_state=SESSION if os.path.exists(SESSION) else None)
        page = ctx.new_page()
        page.on("response", on_resp)

        page.goto(HOME, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        txt = page.evaluate("() => (document.body?document.body.innerText:'')")
        print(f"首页正文 {len(txt)} 字；登录框还在？ "
              f"{bool(re.search(r'(立即登录|短信登录|请输入手机号)', txt))}")

        # 1) 尝试点开右上角头像
        opened = False
        for sel in AVATAR_SEL:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                loc.click(timeout=2500)
                page.wait_for_timeout(1500)
                page.screenshot(path=os.path.join(OUT, "avatar_menu.png"))
                items = [t for t in texts(page) if KEY.search(t)]
                print(f"\n--- 点击 {sel} 后的菜单项（命中 {len(items)}）---")
                for it in items[:30]:
                    print("   ·", it[:120])
                if items:
                    opened = True
                break
            except Exception as e:
                print(f"  选择器 {sel} 失败: {type(e).__name__}")
        if not opened:
            print("  未点到头像（或菜单无关键词项）")

        # 2) 逐个试候选 URL
        for u in CAND:
            try:
                page.goto(u, timeout=20000, wait_until="domcontentloaded")
                page.wait_for_timeout(2500)
            except Exception as e:
                print(f"\n[ERR] {u}: {type(e).__name__}")
                continue
            t = page.evaluate("() => (document.body?document.body.innerText:'')")
            hits = [x for x in texts(page) if KEY.search(x)]
            name = re.sub(r"[^\w]+", "_", u)[-50:]
            try:
                page.screenshot(path=os.path.join(OUT, name + ".png"))
            except Exception:
                pass
            print(f"\n== {u}")
            print(f"   最终 url: {page.url}")
            print(f"   正文 {len(t)} 字: {re.sub(chr(92)+'s+', ' ', t)[:220]}")
            print(f"   命中关键词元素 {len(hits)}")
            for h in hits[:12]:
                print("     ·", h[:110])

        print(f"\n===== 汇总：捕获接口 {len(captured)} 条 =====")
        br.close()


if __name__ == "__main__":
    main()
