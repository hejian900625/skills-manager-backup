# 京东订单页「时间下拉 + 下载按钮」二段探测（临时诊断用，带重试/回退）
# 目的：
#   1) 点开“近3个月订单”那个 select，dump 弹出的时间选项（今年/某年/全部）
#   2) dump 筛选区里那个可疑的“下载”元素结构（可能是个导出按钮）
# 复用登录态：数据结果/jd_session.json（坏/过期会自动回退到重新扫码）
import os
import json
import time
import traceback
from playwright.sync_api import sync_playwright

URL = "https://order.jd.com/center/list.action"
OUT_DIR = "数据结果"
STATE = os.path.join(OUT_DIR, "jd_session.json")
LOGIN_MARKERS = ["text=订单中心", "text=我的订单", "#orderLite", "[class*='orderCard-']"]

DUMP_OPTIONS_JS = r"""
() => {
  const out = {};
  const all = Array.from(document.querySelectorAll('*'));
  out.options = [];
  for (const e of all) {
    const t = (e.innerText || '').trim();
    if (!t || t.length > 16) continue;
    if (/^(近3个月|近三个月|近半年|近1年|近一年|今年|全部|全部订单|20\d{2}年?)$/.test(t)) {
      const r = e.getBoundingClientRect();
      out.options.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,140),
                         text: t, visible: r.width > 0 && r.height > 0,
                         x: Math.round(r.x), y: Math.round(r.y) });
    }
    if (out.options.length >= 60) break;
  }
  out.layers = [];
  document.querySelectorAll("[class*=option],[class*=dropdown],[class*=popover],[class*=menu],[class*=popper],[class*=layer]")
    .forEach(e => {
      const t = (e.innerText||'').trim();
      const r = e.getBoundingClientRect();
      if (out.layers.length < 30 && r.width > 0 && t.length <= 120)
        out.layers.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,140),
                          text: t.slice(0,120), html: (e.outerHTML||'').slice(0, 600) });
    });
  return out;
}
"""

DUMP_DOWNLOAD_JS = r"""
() => {
  const out = {};
  const all = Array.from(document.querySelectorAll('*'));
  const el = all.find(e => (e.innerText||'').trim() === '下载');
  out.found = !!el;
  out.chain = [];
  let cur = el;
  for (let i = 0; i < 6 && cur; i++) {
    out.chain.push({ tag: cur.tagName, cls: (cur.className||'').toString().slice(0,150),
                     id: cur.id||null, html: (cur.outerHTML||'').slice(0, 800) });
    cur = cur.parentElement;
  }
  const fo = document.querySelector('[class*="filterOptions-"]');
  out.filterOptionsChildren = fo ? Array.from(fo.children).map(c => ({
      tag: c.tagName, cls: (c.className||'').toString().slice(0,140),
      text: (c.innerText||'').trim().slice(0,80) })) : [];
  return out;
}
"""


def has_login_cookie(context):
    """京东登录成功的硬判据：Cookie 里有 pt_key（扫码成功即写入）。"""
    try:
        for c in context.cookies():
            if c.get("name") == "pt_key" and c.get("value"):
                return True
    except Exception:
        pass
    return False


def ensure_logged_in(context, page, timeout_s=300):
    """等登录：以 pt_key Cookie 为准（不依赖页面自动跳转）。
    返回 True/False。登录成功后**显式**跳回订单页。"""
    print(f">>> 请扫码登录京东（最多等 {timeout_s} 秒；已登录会立即通过）…")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if has_login_cookie(context):
            print(">>> 检测到登录成功（pt_key Cookie 已写入）")
            break
        # 兜底：页面已经不在登录页且出现订单元素，也算登录成功
        try:
            on_login = "passport.jd.com" in page.url or "login" in page.url.lower()
            if not on_login:
                for m in LOGIN_MARKERS:
                    if page.query_selector(m):
                        print(">>> 检测到已进入订单页")
                        return True
        except Exception:
            pass
        time.sleep(2)
    else:
        print("!! 超时未检测到登录（pt_key 未出现）")
        return False

    # 关键：扫码后页面常停在 passport 不自动跳 → 显式跳订单页
    print(">>> 显式跳转到订单页…")
    for attempt in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded")
            break
        except Exception as e:
            print(f"!! 跳转第 {attempt+1} 次失败: {type(e).__name__}: {str(e)[:100]}")
            time.sleep(2)
    time.sleep(4)
    print(">>> 当前 URL:", page.url)
    return True


def open_and_goto(p, use_state):
    """开浏览器 + 上下文 + goto，返回 (browser, context, page) 或 (browser, None, None)。"""
    browser = p.chromium.launch(headless=False)
    try:
        context = browser.new_context(storage_state=STATE) if use_state else browser.new_context()
    except Exception as e:
        print(f"!! new_context(use_state={use_state}) 失败: {type(e).__name__}: {e}")
        browser.close()
        return None, None, None
    page = context.new_page()
    page.set_default_timeout(180000)
    for attempt in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded")
            return browser, context, page
        except Exception as e:
            print(f"!! goto 第 {attempt+1} 次失败: {type(e).__name__}: {str(e)[:120]}")
            time.sleep(3)
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
    return None, None, None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    have = os.path.exists(STATE)
    print(f">>> 登录态文件: {'有' if have else '无'} ({STATE})")

    with sync_playwright() as p:
        # 先试带登录态，失败再试干净上下文
        browser = context = page = None
        if have:
            browser, context, page = open_and_goto(p, use_state=True)
        if page is None:
            print(">>> 带登录态启动失败，改用干净上下文重新扫码…")
            browser, context, page = open_and_goto(p, use_state=False)
        if page is None:
            print("!! 浏览器始终无法打开（可能是进程锁/被杀）。请先关掉所有残留的 Chromium 窗口再重试。")
            return

        print(">>> 登录（有登录态会自动跳过）…")
        ok = ensure_logged_in(context, page, 300)
        if not ok and have:
            print(">>> 登录态无效，改用干净上下文重新扫码…")
            try:
                context.close(); browser.close()
            except Exception:
                pass
            browser, context, page = open_and_goto(p, use_state=False)
            if page is None:
                print("!! 重开浏览器失败，退出")
                return
            ok = ensure_logged_in(context, page, 300)
        if not ok:
            print("!! 未登录成功，退出")
            try:
                context.close(); browser.close()
            except Exception:
                pass
            return
        try:
            context.storage_state(path=STATE)
            print(">>> 登录态已更新保存")
        except Exception:
            pass
        time.sleep(3)

        data = {}
        data["download"] = page.evaluate(DUMP_DOWNLOAD_JS)

        sel = None
        for cand in ['[class*="selectContainer-"] [class*="select-"]',
                     '[class*="selectContainer-"]',
                     '[class*="select-"]']:
            try:
                el = page.query_selector(cand)
                if el:
                    el.click()
                    sel = cand
                    break
            except Exception:
                continue
        print(f">>> 点击时间下拉 selector = {sel}")
        time.sleep(2)

        data["timeOptions"] = page.evaluate(DUMP_OPTIONS_JS)
        data["clickedSelector"] = sel

        with open("probe_jd_range2.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("=== 下载元素 ===")
        print(json.dumps(data["download"], ensure_ascii=False, indent=2))
        print("=== 时间下拉候选项 ===")
        print(json.dumps(data["timeOptions"], ensure_ascii=False, indent=2))
        print(">>> 结果写入 probe_jd_range2.json")
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
