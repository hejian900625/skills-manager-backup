# 拼多多 H5 订单页可用性探测（无头，无需扫码，纯取证）
# 目的：确认 mobile.yangkeduo.com/orders.html 到底是
#   (a) 登录墙（要手机号+验证码）  (b) 直接可读  (c) 强制跳 App
# 并 dump 真实接口地址，判断有没有可自动化的路子。
import json
import os
import time
import traceback

from playwright.sync_api import sync_playwright

OUT = "数据结果"
URL = "https://mobile.yangkeduo.com/orders.html"
UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
      "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

report = {"final_url": None, "title": None, "text_head": None,
          "requests": [], "api_like": [], "cookies": [], "error": None}


def main():
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width": 390, "height": 844},
                                  is_mobile=True, has_touch=True,
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        page = ctx.new_page()

        def on_req(r):
            try:
                u = r.url
                if "yangkeduo.com" in u or "pinduoduo" in u:
                    report["requests"].append({"m": r.method, "u": u[:200]})
                    if ("/api/" in u) or ("proxy" in u) or r.method == "POST":
                        report["api_like"].append({"m": r.method, "u": u[:220],
                                                   "post": (r.post_data or "")[:400]})
            except Exception:
                pass

        page.on("request", on_req)

        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(6000)
            report["final_url"] = page.url
            try:
                report["title"] = page.title()
            except Exception:
                pass
            try:
                report["text_head"] = page.evaluate(
                    "() => (document.body ? document.body.innerText : '').slice(0,1500)")
            except Exception:
                pass
        except Exception as e:
            report["error"] = f"{type(e).__name__}: {e}"

        try:
            report["cookies"] = [{"name": c.get("name"), "domain": c.get("domain")}
                                 for c in ctx.cookies()]
        except Exception:
            pass
        try:
            page.screenshot(path=os.path.join(OUT, "pdd_probe.png"), full_page=False)
        except Exception:
            pass
        try:
            browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        report["error"] = traceback.format_exc()[-1200:]
    with open(os.path.join("数据结果", "pdd_probe.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("final_url:", report["final_url"])
    print("title:", report["title"])
    print("error:", report["error"])
    print("cookies:", len(report["cookies"]))
    print("requests:", len(report["requests"]))
    print("api_like:", len(report["api_like"]))
    for a in report["api_like"][:12]:
        print("  ", a["m"], a["u"][:150])
    print("--- text head ---")
    print((report["text_head"] or "")[:800])
