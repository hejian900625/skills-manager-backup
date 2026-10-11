# 拼多多 H5 订单页探测（有头，需你输一次手机号+短信验证码）
# 目的：确认手机登录后 mobile.yangkeduo.com/orders.html 到底能给什么：
#   ① 有没有订单卡片、长什么样
#   ② 有没有「筛选 / 时间范围（全部时间）」→ 决定能否拿到早期订单
#   ③ 有没有「导出」按钮
#   ④ 真实接口地址
# 产物（数据结果/）：pdd_login.json / pdd_orders_dom.html / pdd_orders.png
#
# 说明：拼多多 H5 只支持「手机号 + 短信验证码」登录（没有扫码），风控也比淘宝/京东严，
#      所以这一步只做「取证」，失败也不影响其它平台。
import json
import os
import re
import time
import traceback

from playwright.sync_api import sync_playwright

OUT = "数据结果"
ORDERS_URL = "https://mobile.yangkeduo.com/orders.html"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
STATE = os.path.join(OUT, "pdd_session.json")

report = {"login_url": None, "after_url": None, "title": None, "text_head": None,
          "card_hits": {}, "filter_found": False, "filter_dump": None,
          "export_found": False, "requests": [], "cookies": [], "error": None}


def has_login_cookie(ctx):
    """拼多多 H5 登录成功后会出现带 access token 的 Cookie。"""
    try:
        names = {c.get("name", "") for c in ctx.cookies()}
        for n in names:
            low = n.lower()
            if "accesstoken" in low or "pdd_user_id" in low or low == "pdd_id":
                return True
    except Exception:
        pass
    return False


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        kw = {"user_agent": UA, "viewport": {"width": 390, "height": 844},
              "is_mobile": True, "has_touch": True,
              "locale": "zh-CN", "timezone_id": "Asia/Shanghai"}
        ctx = browser.new_context(storage_state=STATE, **kw) if os.path.exists(STATE) \
            else browser.new_context(**kw)
        page = ctx.new_page()
        page.set_default_timeout(40000)

        def on_req(r):
            try:
                u = r.url
                if "yangkeduo.com" in u or "pinduoduo.com" in u:
                    report["requests"].append({"m": r.method, "u": u[:200],
                                               "post": (r.post_data or "")[:300]})
            except Exception:
                pass

        page.on("request", on_req)

        page.goto(ORDERS_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        report["login_url"] = page.url
        print(">>> 当前 URL:", page.url)

        # ---- 等登录（手机号 + 短信验证码；最多 6 分钟）----
        print(">>> 请在弹出的窗口里用【手机号 + 短信验证码】登录拼多多（最多等 360 秒）…")
        deadline = time.time() + 360
        last = -1
        while time.time() < deadline:
            if has_login_cookie(ctx) or "login.html" not in page.url:
                print(">>> 检测到登录成功")
                break
            w = int(360 - (deadline - time.time()))
            if w // 10 != last:
                last = w // 10
                print(f"    [{w}s] URL={page.url[:100]}")
            page.wait_for_timeout(2000)
        else:
            print("!! 超时未检测到登录")
            report["error"] = "login timeout"
        try:
            ctx.storage_state(path=STATE)
            print(">>> 登录态已保存:", STATE)
        except Exception:
            pass

        # ---- 回到订单页并取证 ----
        for _ in range(3):
            try:
                page.goto(ORDERS_URL, wait_until="domcontentloaded")
                break
            except Exception:
                page.wait_for_timeout(2000)
        page.wait_for_timeout(5000)
        report["after_url"] = page.url
        try:
            report["title"] = page.title()
        except Exception:
            pass
        try:
            report["text_head"] = page.evaluate(
                "() => (document.body?document.body.innerText:'').slice(0,3000)")
        except Exception:
            pass

        # 订单卡片候选选择器命中数
        cands = {"[class*='order']": "[class*='order']",
                 "[class*='Order']": "[class*='Order']",
                 "a[href*='order_detail']": "a[href*='order_detail']",
                 "[class*='goods']": "[class*='goods']"}
        for name, sel in cands.items():
            try:
                report["card_hits"][name] = page.eval_on_selector_all(sel, "e=>e.length")
            except Exception:
                report["card_hits"][name] = -1

        # 找「筛选 / 时间」
        try:
            hit = page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('*').forEach(e => {
                    const t = (e.innerText||'').trim();
                    if (t && t.length <= 6 &&
                        ['筛选','全部','全部时间','近三个月','近3个月','时间'].includes(t)) {
                        const r = e.getBoundingClientRect();
                        out.push({t, cls: (e.className||'').toString().slice(0,60),
                                  x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)});
                    }
                });
                return out.slice(0, 20);
            }""")
            report["filter_found"] = bool(hit)
            report["filter_dump"] = hit
        except Exception:
            pass

        # 找「导出」
        try:
            report["export_found"] = bool(page.evaluate(
                "() => /导出|下载/.test(document.body?document.body.innerText:'')"))
        except Exception:
            pass

        # 保存整页 DOM 供离线分析（关键：省得再让你跑第二次）
        try:
            html = page.content()
            with open(os.path.join(OUT, "pdd_orders_dom.html"), "w", encoding="utf-8") as f:
                f.write(html)
            print(">>> 已保存 DOM:", os.path.join(OUT, "pdd_orders_dom.html"), len(html), "字节")
        except Exception:
            pass
        try:
            page.screenshot(path=os.path.join(OUT, "pdd_orders.png"), full_page=False)
        except Exception:
            pass
        try:
            report["cookies"] = [c.get("name") for c in ctx.cookies()]
        except Exception:
            pass

        print(">>> 取证完成，按回车关闭浏览器…")
        try:
            input()
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        report["error"] = "KeyboardInterrupt"
        print("\n>>> 已中断")
    except Exception:
        report["error"] = traceback.format_exc()[-1500:]
        traceback.print_exc()
        try:
            input(">>> 出错了，按回车关闭…")
        except Exception:
            pass
    with open(os.path.join(OUT, "pdd_login.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("=== 摘要 ===")
    print("after_url:", report["after_url"])
    print("title:", report["title"])
    print("card_hits:", report["card_hits"])
    print("filter_found:", report["filter_found"], "| export_found:", report["export_found"])
    print("error:", report["error"])
