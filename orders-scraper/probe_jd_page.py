# 京东订单页「翻页/加载更多」四段探测（临时诊断用）
# 目的：某年份订单 >20 条时，找出如何加载第 2 页（滚动？点击？内层滚动容器？）
# 手段：先切到「2022年订单」(totalNum=81, 只返回20) → 试多种加载策略 → 每次都看 API 请求数变化
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
TARGET_RANGE = "2022年订单"      # 有 81 单，只显示 20 → 必然要翻页

DUMP_JS = r"""
() => {
  const out = {};
  out.orderCards = document.querySelectorAll('[class*="orderCard-"]').length;
  // 可滚动容器
  out.scrollers = [];
  document.querySelectorAll('*').forEach(e => {
    if (e.scrollHeight > e.clientHeight + 40 && e.clientHeight > 100 && out.scrollers.length < 15) {
      const r = e.getBoundingClientRect();
      out.scrollers.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,120),
        scrollTop: e.scrollTop, scrollHeight: e.scrollHeight, clientHeight: e.clientHeight,
        x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) });
    }
  });
  // 分页/加载更多候选
  out.pager = [];
  document.querySelectorAll('[class*=pag],[class*=page],[class*=more],[class*=load]').forEach(e => {
    const t = (e.innerText||'').trim();
    const r = e.getBoundingClientRect();
    if (out.pager.length < 30)
      out.pager.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,120),
        text: t.slice(0,40), visible: r.width>0 && r.height>0 });
  });
  // 全页短文本里含“下一页/加载更多/查看更多/上一页”的
  out.textHits = [];
  const all = Array.from(document.querySelectorAll('*'));
  for (const e of all) {
    const t = (e.innerText||'').trim();
    if (!t || t.length > 12) continue;
    if (/下一页|上一页|加载更多|查看更多|更多|收起|^\d+$/.test(t)) {
      const r = e.getBoundingClientRect();
      if (r.width>0 && r.height>0) out.textHits.push({ tag:e.tagName, cls:(e.className||'').toString().slice(0,120),
        text:t, x:Math.round(r.x), y:Math.round(r.y) });
    }
    if (out.textHits.length >= 40) break;
  }
  out.docScroll = { scrollTop: document.scrollingElement ? document.scrollingElement.scrollTop : -1,
                    scrollHeight: document.scrollingElement ? document.scrollingElement.scrollHeight : -1,
                    clientHeight: document.scrollingElement ? document.scrollingElement.clientHeight : -1 };
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
    """等登录：以 pt_key Cookie 为准 + 打印实时进度（避免看起来像卡死）。"""
    print(f">>> 检查登录态（最多等 {timeout_s} 秒）…")
    deadline = time.time() + timeout_s
    waited = 0
    last_report = -1
    while time.time() < deadline:
        if has_login_cookie(context):
            print(">>> ✅ 检测到登录成功（pt_key Cookie）")
            break
        # 每 5 秒报一次状态
        if waited // 5 != last_report:
            last_report = waited // 5
            try:
                url = page.url
            except Exception:
                url = "(取不到)"
            login_page = ("passport.jd.com" in url) or ("login" in url.lower())
            try:
                n_ok = len(context.cookies())
            except Exception:
                n_ok = -1
            print(f"    [{waited}s] URL={url[:90]}")
            print(f"          cookie数={n_ok}  登录页={'是（请扫码）' if login_page else '否'}")
        # 兜底：不在登录页且出现订单元素
        try:
            if "passport.jd.com" not in page.url and "login" not in page.url.lower():
                for m in LOGIN_MARKERS:
                    if page.query_selector(m):
                        print(">>> ✅ 页面已是订单页")
                        return True
        except Exception:
            pass
        time.sleep(2)
        waited += 2
    else:
        print("!! 超时未检测到登录（pt_key 未出现）。若页面上有二维码请扫码后再跑一次。")
        return False

    for _ in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded"); break
        except Exception:
            time.sleep(2)
    time.sleep(4)
    print(">>> 当前 URL:", page.url)
    return True


def open_dropdown(page):
    el = page.query_selector('[class*="selectContainer-"]')
    if not el:
        return []
    box = el.bounding_box()
    if not box:
        return []
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    time.sleep(1.6)
    try:
        return page.eval_on_selector_all('[class*="selectList-"] [class*="item-"]',
                                         "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean)")
    except Exception:
        return []


def click_option(page, text):
    pos = page.evaluate("""(t) => {
        const els = document.querySelectorAll('[class*="selectList-"] [class*="item-"]');
        for (const e of els) if ((e.innerText||'').trim() === t) {
            e.scrollIntoView({block:'center'});
            const r = e.getBoundingClientRect();
            return {x: r.x + r.width/2, y: r.y + r.height/2};
        }
        return null;
    }""", text)
    if not pos:
        return False
    page.mouse.click(pos["x"], pos["y"])
    return True


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        have = os.path.exists(STATE)
        context = browser.new_context(storage_state=STATE) if have else browser.new_context()
        page = context.new_page()
        page.set_default_timeout(180000)

        reqs = []

        def on_request(r):
            try:
                if "api.m.jd.com" in r.url and "functionId=pcorder_center_list" in r.url:
                    reqs.append(r.post_data)
            except Exception:
                pass

        page.on("request", on_request)

        try:
            page.goto(URL, wait_until="domcontentloaded")
        except Exception:
            pass
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
        try:
            page.evaluate("""() => document.querySelectorAll('[class*="tooltipFilter-"]').forEach(e=>e.remove())""")
        except Exception:
            pass
        time.sleep(1)

        # 切到目标范围
        opts = open_dropdown(page)
        print(">>> 选项:", opts)
        if TARGET_RANGE in opts:
            click_option(page, TARGET_RANGE)
            print(f">>> 已切换到 {TARGET_RANGE}")
        else:
            print(f"!! 未找到 {TARGET_RANGE}")
        time.sleep(4)

        report = {"target": TARGET_RANGE, "steps": []}

        def snap(tag):
            d = page.evaluate(DUMP_JS)
            d["api_requests"] = list(reqs)
            report["steps"].append({"tag": tag, **d})
            print(f"\n--- [{tag}] orderCards={d['orderCards']} api请求数={len(reqs)} "
                  f"scrollTop={d['docScroll']['scrollTop']}/{d['docScroll']['scrollHeight']}")
            return d

        base = snap("base")

        # 策略1：鼠标移到列表中央后滚动
        print("\n>>> 策略1：鼠标移到列表中央滚轮")
        page.mouse.move(600, 400)
        for _ in range(4):
            page.mouse.wheel(0, 3000)
            time.sleep(1.2)
        s1 = snap("wheel_at_list")

        # 策略2：把每个可滚动容器滚到底
        print("\n>>> 策略2：JS 滚动所有容器到底")
        page.evaluate("""() => {
            document.querySelectorAll('*').forEach(e => {
                if (e.scrollHeight > e.clientHeight + 40) e.scrollTop = e.scrollHeight;
            });
            if (document.scrollingElement) document.scrollingElement.scrollTop = document.scrollingElement.scrollHeight;
            window.scrollTo(0, document.body.scrollHeight);
        }""")
        time.sleep(2)
        s2 = snap("js_scroll_bottom")

        # 策略3：点击“下一页/加载更多/查看更多/更多”
        print("\n>>> 策略3：点击 下一页/加载更多/查看更多")
        clicked = []
        for label in ["下一页", "加载更多", "查看更多", "更多"]:
            try:
                loc = page.locator(f"text={label}")
                n = loc.count()
                for i in range(min(n, 3)):
                    try:
                        loc.nth(i).click(timeout=2500)
                        clicked.append(label)
                        time.sleep(2.5)
                    except Exception:
                        pass
            except Exception:
                pass
        s3 = snap(f"click_{clicked}")

        # 截图
        try:
            page.screenshot(path=os.path.join(OUT_DIR, "probe4_list.png"), full_page=True)
            print(">>> 截图 probe4_list.png")
        except Exception:
            pass

        with open("probe_jd_page.json", "w", encoding="utf-8") as f:
            json.dump({"report": report, "base": base, "html_pager": (page.evaluate(DUMP_JS)).get("pager")},
                      f, ensure_ascii=False, indent=2)
        print("\n=== base.pager ===")
        print(json.dumps(base.get("pager"), ensure_ascii=False, indent=2))
        print("=== base.scrollers ===")
        print(json.dumps(base.get("scrollers"), ensure_ascii=False, indent=2))
        print("=== base.textHits ===")
        print(json.dumps(base.get("textHits"), ensure_ascii=False, indent=2))
        print(">>> 结果写入 probe_jd_page.json")
        try:
            input(">>> 按回车关闭浏览器…")
        except Exception:
            pass
        try:
            context.close(); browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n>>> 已中断（Ctrl+C）。")
    except Exception:
        traceback.print_exc()
        try:
            input(">>> 出错了，按回车关闭…")
        except Exception:
            pass
