# 高德订单/轨迹「登录取证」——有头浏览器，用户手动登录一次
# 目的：登录后回答三件事
#   1. 高德网页版有没有「我的订单 / 行程记录」（打车订单）？
#   2. 「足迹 / 轨迹」页能不能拿到数据（起终点、时间、里程）？
#   3. 数据从哪个接口来？能不能规模化导出？
#
# 用法：python probe_amap_login.py
# 产出：数据结果/amap_session.json（登录态）、amap_probe/*.html、amap_api/*.json
import json
import os
import re
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\Lenovo\数据结果\amap_probe"
API = r"C:\Users\Lenovo\数据结果\amap_api"
SESSION = r"C:\Users\Lenovo\数据结果\amap_session.json"
os.makedirs(OUT, exist_ok=True)
os.makedirs(API, exist_ok=True)

HOME = "https://www.amap.com/"
CANDIDATES = [
    ("myfoot", "https://www.amap.com/myfoot"),
]

KEY = re.compile(r"(订单|行程|足迹|轨迹|我的|打车|出行|记录)", re.I)
API_KEY = re.compile(r"(order|trip|foot|track|journey|history|route|drive)", re.I)

captured = []


def logged_in(page):
    """严格判据：页面不再出现登录框，才算登录。

    教训（第一次跑踩的坑）：localStorage 里的 `amap-uuid` **匿名访问也有**，
    拿它当登录凭据会立刻误判成"已登录"，导致整轮取证跑在匿名态下。
    """
    try:
        txt = page.evaluate("() => (document.body?document.body.innerText:'')")
    except Exception:
        return False, {}
    # 0) 页面还没渲染出来 → 什么都判断不了，继续等（上次就是在这一帧误判的）
    if len(txt) < 50:
        return False, {}
    # 1) 登录框还在 → 一定没登录（这是唯一可信的负判据）
    if re.search(r"(立即登录|短信登录|二维码登录|发送验证码|请输入手机号)", txt):
        return False, {}
    # 2) 登录框消失 → 认为已登录
    st = {"len": len(txt), "head": re.sub(r"\s+", " ", txt)[:200]}
    return True, st


def on_response(resp):
    try:
        u = resp.url
        if not API_KEY.search(u):
            return
        ct = ""
        try:
            ct = (resp.headers or {}).get("content-type", "")
        except Exception:
            pass
        body = ""
        if "json" in ct:
            try:
                body = resp.text()[:200000]
            except Exception:
                pass
        rec = {"url": u, "status": resp.status, "ct": ct, "body": body}
        captured.append(rec)
        with open(os.path.join(API, f"cap_{len(captured):02d}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False)
        print(f"  [API {len(captured):>2}] {resp.status} {u[:130]}"
              f"  ({len(body)}B)")
    except Exception:
        pass


def dump_page(page, name):
    try:
        page.wait_for_timeout(3500)
    except Exception:
        pass
    html = page.content()
    with open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8") as f:
        f.write(html)
    try:
        page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=False)
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
    print(f"  正文 : {len(txt)} 字")
    print("  正文片段: " + re.sub(r"\s+", " ", txt)[:500])
    print(f"  链接 : {len(links)} 个，命中 {len(hits)}")
    for h in hits[:25]:
        print(f"     · {h[:130]}")
    return hits


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1440, "height": 900},
            storage_state=SESSION if os.path.exists(SESSION) else None,
        )
        page = ctx.new_page()
        page.on("response", on_response)

        page.goto(HOME, timeout=30000, wait_until="domcontentloaded")
        ok, st = logged_in(page)
        if not ok:
            print("\n>>> 请在弹出的浏览器里登录高德（手机号+验证码，或高德 App 扫码）")
            print(">>> 若出现滑块验证，手动拖一下。检测到真实登录态后脚本自动继续。\n")
            for i in range(160):          # 最多等 8 分钟
                page.wait_for_timeout(3000)
                if i % 5 == 0:
                    print(f"    ...等待登录（{(i+1)*3}s）", flush=True)
                ok, st = logged_in(page)
                if ok:
                    break
        print(f"\n登录态: {'已登录' if ok else '未登录（继续匿名抓取）'}")
        print("  可见凭据键:", list((st or {}).get("ls", {}).keys())[:8])

        try:
            ctx.storage_state(path=SESSION)
            print("  已保存登录态 ->", SESSION)
        except Exception as e:
            print("  保存登录态失败:", e)

        hits = dump_page(page, "home_logged")
        urls = []
        for h in hits:
            m = re.search(r"(https?://[^\s]+)", h)
            if m:
                urls.append(m.group(1))
        urls = [u for u in urls if "amap.com" in u][:6]

        seen = set()
        for name, u in CANDIDATES + [("", x) for x in urls]:
            if u in seen or not u:
                continue
            seen.add(u)
            try:
                page.goto(u, timeout=25000, wait_until="domcontentloaded")
                dump_page(page, re.sub(r"[^\w]+", "_", u)[-60:])
            except Exception as e:
                print(f"  [ERR] {u}: {type(e).__name__}: {e}")

        print(f"\n===== 汇总 =====")
        print(f"  捕获接口 {len(captured)} 条，已写入 {API}")
        br.close()


if __name__ == "__main__":
    main()
