# 美团订单中心 H5 登录 + 取证 —— 有头，需人工输手机号+验证码。
# 目的：一次跑完，回答「登录后订单数据从哪来、能不能规模化导出」。
#   ① 订单中心页 DOM / 文本；② 全部 XHR 请求（找订单接口）；③ 页面内嵌全局数据；
#   ④ 下拉加载更多是否触发新请求；⑤ 存登录态供后续复用。
# 跑法（在 C:/Users/Lenovo 下跑，产出落到 数据结果/）：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe "C:/Users/Lenovo/.workbuddy/skills/orders_scraper/probe_mt_login.py"
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

OUT = "数据结果"
ORDER_URL = "https://i.meituan.com/mttouch/page/order"
STATE = os.path.join(OUT, "mt_session.json")

H5_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
         "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

LOGIN_COOKIE_HINTS = ("token", "userid", "user_id", "mt_c_token")


def has_login(ctx):
    try:
        names = {c.get("name", "").lower() for c in ctx.cookies()}
        return any(any(h in n for h in LOGIN_COOKIE_HINTS) for n in names)
    except Exception:
        return False


def dump(page, reqs, tag):
    print(f"\n===== 取证 [{tag}]")
    print("  url   :", page.url)
    try:
        print("  title :", page.title())
    except Exception:
        pass
    try:
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:
        text = ""
    text = re.sub(r"\n{2,}", "\n", (text or "").strip())
    print(f"  text({len(text)}字):", text[:700].replace("\n", " | "))
    for k in ("我的订单", "全部订单", "待付款", "待收货", "待评价", "退款", "外卖", "门票", "酒店", "暂无"):
        if k in text:
            print("   · 命中:", k)
    try:
        html = page.content()
        p = os.path.join(OUT, f"mt_{tag}.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  DOM 已存: {p}（{len(html)} 字节）")
    except Exception as e:
        print("  DOM 保存失败:", type(e).__name__)
    try:
        png = os.path.join(OUT, f"mt_{tag}.png")
        page.screenshot(path=png, full_page=False)
        print("  截图已存:", png)
    except Exception:
        pass
    try:
        gl = page.evaluate("""() => {
            const keys = [];
            for (const k of Object.keys(window)) {
                try {
                    const v = window[k];
                    if (v && typeof v === 'object' &&
                        /raw|INITIAL|store|Store|data|Data/i.test(k)) keys.push(k);
                } catch(_) {}
            }
            return keys.slice(0, 40);
        }""")
        print("  疑似全局状态变量:", gl)
    except Exception:
        pass
    api = [u for u in dict.fromkeys(reqs)
           if re.search(r"/api/|gateway|order|/wm/", u, re.I)
           and "catfront" not in u and "portal-portm" not in u]
    print(f"  疑似业务接口 {len(api)} 个：")
    for u in api[:35]:
        print("    ", u[:170])


def main():
    os.makedirs(OUT, exist_ok=True)
    have = os.path.exists(STATE)
    print(">>> 登录态文件:", STATE, "（存在，尝试复用）" if have else "（不存在，需登录）")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False,
                                    args=["--disable-blink-features=AutomationControlled"])
        kw = {"user_agent": H5_UA, "viewport": {"width": 390, "height": 844},
              "is_mobile": True, "has_touch": True,
              "locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
        ctx = browser.new_context(storage_state=STATE, **kw) if have else browser.new_context(**kw)
        page = ctx.new_page()
        page.set_default_timeout(40000)

        reqs = []
        page.on("request", lambda r: reqs.append(r.url))

        try:
            page.goto(ORDER_URL, wait_until="domcontentloaded")
        except Exception as e:
            print("!! 打开失败:", type(e).__name__, e)
        page.wait_for_timeout(5000)
        print(">>> 当前 URL:", page.url)

        if not has_login(ctx) or "passport.meituan.com" in page.url or "login" in page.url:
            print("\n>>> 请在浏览器窗口里用【手机号 + 短信验证码】登录美团。")
            print(">>> 若出现滑块/拼图验证，请手动拖动完成。最多等 300 秒…")
            deadline = time.time() + 300
            last = -1
            while time.time() < deadline:
                if has_login(ctx) and "passport.meituan.com" not in page.url:
                    print(">>> 检测到登录成功")
                    break
                w = int(300 - (deadline - time.time()))
                if w // 10 != last:
                    last = w // 10
                    print(f"    [{w}s] 等待登录… URL={page.url[:100]}")
                page.wait_for_timeout(2000)
            else:
                print("!! 超时未登录")
            try:
                ctx.storage_state(path=STATE)
                print(">>> 登录态已保存:", STATE)
            except Exception:
                pass
            try:
                page.goto(ORDER_URL, wait_until="domcontentloaded")
            except Exception:
                pass
            page.wait_for_timeout(6000)

        reqs.clear()
        dump(page, reqs, "order_center")

        # 下拉加载更多，看是否触发新请求
        print("\n===== 下拉加载探测")
        page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3500)
        page.mouse.wheel(0, 3000)
        page.wait_for_timeout(3500)
        new = [u for u in dict.fromkeys(reqs)
               if re.search(r"/api/|gateway|order|/wm/", u, re.I)
               and "catfront" not in u and "portal-portm" not in u]
        print(f"  下拉后业务接口 {len(new)} 个：")
        for u in new[:35]:
            print("    ", u[:170])

        try:
            ctx.storage_state(path=STATE)
        except Exception:
            pass
        print("\n>>> 完成，按回车关闭浏览器…")
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
