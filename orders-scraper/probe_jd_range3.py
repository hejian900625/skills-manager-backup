# 京东订单页「时间下拉」三段探测（截图 + 网络监听，临时诊断用）
# 目的：
#   1) 用多种点击方式真正点开“近3个月订单”下拉
#   2) 点前/点后各截一张图（我看图判断到底有没有展开）
#   3) 监听点击后触发的订单接口请求（postData 里的 d 参数是否随选项变化）
# 复用登录态：数据结果/jd_session.json
import os
import json
import time
import traceback
from playwright.sync_api import sync_playwright

URL = "https://order.jd.com/center/list.action"
OUT_DIR = "数据结果"
STATE = os.path.join(OUT_DIR, "jd_session.json")
LOGIN_MARKERS = ["text=订单中心", "text=我的订单", "#orderLite", "[class*='orderCard-']"]

# 广谱 dump：点开下拉后，把所有“像选项/弹层”的可视元素抓出来
DUMP_POPUP_JS = r"""
() => {
  const out = { visible_texts: [], popups: [], select_html: null };
  const all = Array.from(document.querySelectorAll('*'));
  // 1) 所有可视且文字很短的叶子元素（候选选项）
  for (const e of all) {
    const t = (e.innerText || '').trim();
    if (!t || t.length > 20) continue;
    if (e.children.length > 0) continue;           // 只看叶子
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) continue;
    if (r.y < 60 || r.y > 700) continue;           // 只看首屏主要内容区
    out.visible_texts.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,120),
                             text: t, x: Math.round(r.x), y: Math.round(r.y) });
  }
  // 2) 弹层类容器（新出现的面板）
  document.querySelectorAll("[class*=popup],[class*=panel],[class*=dialog],[class*=modal],[class*=popper],[class*=dropdown],[class*=option],[class*=list]")
    .forEach(e => {
      const r = e.getBoundingClientRect();
      const t = (e.innerText||'').trim();
      if (out.popups.length < 25 && r.width > 0 && r.height > 0 && t.length <= 200)
        out.popups.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,140),
                          text: t.slice(0,200), html: (e.outerHTML||'').slice(0,700) });
    });
  // 3) 时间下拉容器完整 HTML
  const sc = document.querySelector('[class*="selectContainer-"]');
  if (sc) out.select_html = (sc.parentElement ? sc.parentElement.outerHTML : sc.outerHTML).slice(0, 2500);
  return out;
}
"""


AUTH_COOKIE_NAMES = ("pt_key", "pin")   # PC 端登录用 pin（pt_key 是手机端）


def has_login_cookie(context):
    try:
        names = {c.get("name") for c in context.cookies()}
        for n in AUTH_COOKIE_NAMES:
            if n in names:
                return True
    except Exception:
        pass
    return False


def ensure_logged_in(context, page, timeout_s=300):
    print(f">>> 请扫码登录京东（最多等 {timeout_s} 秒；已登录会立即通过）…")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if has_login_cookie(context):
            print(">>> 检测到登录成功（pt_key）")
            break
        try:
            if "passport.jd.com" not in page.url and "login" not in page.url.lower():
                for m in LOGIN_MARKERS:
                    if page.query_selector(m):
                        print(">>> 已在订单页")
                        return True
        except Exception:
            pass
        time.sleep(2)
    else:
        print("!! 超时未登录")
        return False
    for attempt in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(f"!! 跳转失败({attempt+1}): {type(e).__name__}")
            time.sleep(2)
    time.sleep(4)
    print(">>> 当前 URL:", page.url)
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        have = os.path.exists(STATE)
        context = browser.new_context(storage_state=STATE) if have else browser.new_context()
        page = context.new_page()
        page.set_default_timeout(180000)

        req_log = []

        def on_request(req):
            try:
                if "api.m.jd.com" in req.url and ("order" in req.url.lower()):
                    try:
                        post = req.post_data
                    except Exception:
                        post = None
                    req_log.append({"url": req.url, "post": post})
            except Exception:
                pass

        page.on("request", on_request)

        try:
            page.goto(URL, wait_until="domcontentloaded")
        except Exception as e:
            print("!! goto 失败:", type(e).__name__, e)
        if has_login_cookie(context):
            print(">>> 已有登录态")
        if not ensure_logged_in(context, page, 300):
            try:
                context.close(); browser.close()
            except Exception:
                pass
            return
        try:
            context.storage_state(path=STATE)
        except Exception:
            pass
        time.sleep(2)

        # 关闭可能遮挡的推广横幅（下载桌面版 tooltip）以露出下拉
        try:
            page.evaluate("""() => {
                document.querySelectorAll('[class*="tooltipFilter-"]').forEach(e => e.remove());
            }""")
        except Exception:
            pass
        time.sleep(1)

        page.screenshot(path=os.path.join(OUT_DIR, "probe3_before.png"), full_page=False)
        print(">>> 已截图 probe3_before.png")

        # ---- 点击时间下拉：多策略 ----
        strategies = [
            ("mouse_center", "鼠标点容器中心"),
            ("playwright_force", "Playwright force click"),
            ("js_click", "JS 原生 click"),
            ("js_mouse_events", "JS 派发 mousedown/mouseup/click"),
        ]
        box_info = {}
        results = {}
        for name, desc in strategies:
            print(f"\n--- 尝试点击方式：{name}（{desc}）---")
            req_before = len(req_log)
            try:
                if name == "mouse_center":
                    el = page.query_selector('[class*="selectContainer-"]')
                    if not el:
                        print("  找不到 selectContainer")
                        continue
                    box = el.bounding_box()
                    box_info = box or {}
                    if box:
                        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
                        page.mouse.click(cx, cy)
                        print(f"  点击坐标 ({cx:.0f},{cy:.0f})")
                elif name == "playwright_force":
                    page.click('[class*="selectContainer-"] [class*="select-"]', force=True, timeout=5000)
                elif name == "js_click":
                    page.evaluate("""() => {
                        const el = document.querySelector('[class*="selectContainer-"] [class*="select-"]')
                                 || document.querySelector('[class*="selectContainer-"]');
                        if (el) el.click();
                    }""")
                elif name == "js_mouse_events":
                    page.evaluate("""() => {
                        const el = document.querySelector('[class*="selectContainer-"] [class*="select-"]')
                                 || document.querySelector('[class*="selectContainer-"]');
                        if (!el) return;
                        const r = el.getBoundingClientRect();
                        const opts = {bubbles:true, cancelable:true, view:window,
                                      clientX: r.x + r.width/2, clientY: r.y + r.height/2};
                        el.dispatchEvent(new MouseEvent('mousedown', opts));
                        el.dispatchEvent(new MouseEvent('mouseup', opts));
                        el.dispatchEvent(new MouseEvent('click', opts));
                    }""")
            except Exception as e:
                print(f"  点击异常: {type(e).__name__}: {str(e)[:100]}")
            time.sleep(2.5)

            dump = page.evaluate(DUMP_POPUP_JS)
            # 过滤掉明显的左侧菜单噪声
            opts = [v for v in dump["visible_texts"]
                    if v["text"] not in ("我的订单", "评价晒单", "代下单")]
            years = [v for v in opts if any(k in v["text"] for k in ("年", "近", "全部", "今天", "昨天", "月"))]
            results[name] = {
                "clicked": True,
                "new_requests": req_log[req_before:],
                "year_like": years[:30],
                "popups": [p for p in dump["popups"] if len(p["text"]) <= 60][:10],
            }
            print(f"  点击后新增订单请求数: {len(results[name]['new_requests'])}")
            print(f"  疑似时间选项: {json.dumps(years[:15], ensure_ascii=False)}")
            if years:
                print("  >>> 命中！停止后续尝试")
                page.screenshot(path=os.path.join(OUT_DIR, "probe3_after.png"), full_page=False)
                break

        if not os.path.exists(os.path.join(OUT_DIR, "probe3_after.png")):
            page.screenshot(path=os.path.join(OUT_DIR, "probe3_after.png"), full_page=False)
        print(">>> 已截图 probe3_after.png")

        final_dump = page.evaluate(DUMP_POPUP_JS)
        out = {
            "box": box_info,
            "results": results,
            "select_html": final_dump.get("select_html"),
            "all_visible_texts": final_dump.get("visible_texts")[:120],
            "all_requests": req_log,
        }
        with open("probe_jd_range3.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(">>> 结果写入 probe_jd_range3.json")
        print(">>> 截图: 数据结果/probe3_before.png , 数据结果/probe3_after.png")
        input(">>> 按回车关闭浏览器…")
        try:
            context.close(); browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input(">>> 出错了，按回车关闭…")
