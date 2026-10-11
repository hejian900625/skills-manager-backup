# 京东订单页「时间范围下拉」探测脚本（临时诊断用）
# 目的：找到“近3个月订单”旁边那个可切“今年/某年/全部”的下拉控件的真实结构，
#       以便在 jd_export.py 里自动切换时间范围、拉更早的历史订单。
# 复用登录态：数据结果/jd_session.json（没有则扫码一次）
import os
import json
import time
from playwright.sync_api import sync_playwright

URL = "https://order.jd.com/center/list.action"
OUT_DIR = "数据结果"
STATE = os.path.join(OUT_DIR, "jd_session.json")
LOGIN_MARKERS = ["text=订单中心", "text=我的订单", "#orderLite", "[class*='orderCard-']"]

PROBE_JS = r"""
() => {
  const out = {};
  const all = Array.from(document.querySelectorAll('*'));

  // 1) 含“近3个月 / 全部订单 / 时间”的小文本元素
  out.targets = [];
  for (const e of all) {
    const t = (e.innerText || '').trim();
    if (t && t.length <= 14 && /近3个月|近三个月|全部订单|时间筛选/.test(t)) {
      out.targets.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,120),
                         id: e.id||null, text: t.slice(0,30) });
      if (out.targets.length >= 20) break;
    }
  }

  // 2) “近3个月”元素的祖先链（找可点击的下拉容器）
  const el = all.find(e => (e.innerText||'').trim().startsWith('近3个月'));
  out.ancestors = [];
  let cur = el;
  for (let i = 0; i < 6 && cur; i++) {
    out.ancestors.push({ tag: cur.tagName, cls: (cur.className||'').toString().slice(0,150),
                         id: cur.id||null, html: (cur.outerHTML||'').slice(0, 1000) });
    cur = cur.parentElement;
  }

  // 3) 候选控件（下拉/筛选/时间/排序）
  out.controls = [];
  document.querySelectorAll("[class*=drop],[class*=select],[class*=filter],[class*=time],[class*=date],[class*=range],[class*=sort],[role=combobox]")
    .forEach(e => {
      if (out.controls.length < 40)
        out.controls.push({ tag: e.tagName, cls: (e.className||'').toString().slice(0,120),
                            text: (e.innerText||'').trim().slice(0,40) });
    });

  return out;
}
"""


def wait_login(page, timeout_s=300):
    waited = 0
    while waited < timeout_s:
        for m in LOGIN_MARKERS:
            try:
                if page.query_selector(m):
                    return True
            except Exception:
                pass
        time.sleep(3)
        waited += 3
    return False


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        have = os.path.exists(STATE)
        context = browser.new_context(storage_state=STATE) if have else browser.new_context()
        page = context.new_page()
        page.set_default_timeout(180000)
        page.goto(URL)
        print(">>> 登录（有登录态会自动跳过）…")
        ok = wait_login(page, 90 if have else 300)
        if not ok and have:
            context.close()
            context = browser.new_context()
            page = context.new_page()
            page.set_default_timeout(180000)
            page.goto(URL)
            ok = wait_login(page, 300)
        if not ok:
            print("!! 未登录成功，退出")
            context.close(); browser.close(); return
        try:
            context.storage_state(path=STATE)
        except Exception:
            pass
        time.sleep(3)

        data = page.evaluate(PROBE_JS)
        with open("probe_jd_range.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("=== targets（含“近3个月”等的小文本元素）===")
        print(json.dumps(data.get("targets"), ensure_ascii=False, indent=2))
        print("=== ancestors（祖先链，找可点下拉容器）===")
        print(json.dumps(data.get("ancestors"), ensure_ascii=False, indent=2))
        print("=== controls（候选下拉/筛选控件）===")
        print(json.dumps(data.get("controls"), ensure_ascii=False, indent=2))
        print(">>> 结果写入 probe_jd_range.json")
        input(">>> 按回车关闭浏览器…")
        context.close(); browser.close()


if __name__ == "__main__":
    main()
