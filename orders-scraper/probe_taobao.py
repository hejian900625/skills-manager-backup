# 淘宝新版订单页 DOM 探测脚本（临时诊断用，不改动主流程）
# 用法：python probe_taobao.py
# 目的：登录后 dump 订单容器/导出按钮/分页/日期控件的真实 selector，
#       用于改写 taobao.py 中已失效的旧版选择器。
import time
import json
from playwright.sync_api import sync_playwright

URL = "https://buyertrade.taobao.com/trade/itemlist/list_bought_items.htm"

PROBE_JS = r"""
() => {
  const out = {};
  // 1) 所有 id 列表（前 80 个）
  out.ids = Array.from(document.querySelectorAll('[id]')).map(e => e.id).slice(0, 80);

  // 2) 含“订单/宝贝/导出”文本的可点击元素
  const textHits = [];
  document.querySelectorAll('button, a, div[role=button], span').forEach(e => {
    const t = (e.innerText || '').trim();
    if (t && t.length < 12 && /导出|订单|宝贝|筛选|上一页|下一页|搜索/.test(t)) {
      textHits.push({
        tag: e.tagName,
        text: t,
        cls: (e.className || '').toString().slice(0, 120),
        id: e.id || null,
      });
    }
  });
  out.textHits = textHits.slice(0, 60);

  // 3) 疑似订单行容器（class 含 trade/order/item/list 的 div）
  const cand = [];
  document.querySelectorAll('div, table, tbody, ul').forEach(e => {
    const c = (e.className || '').toString();
    if (/trade|order|item|list|bought/i.test(c) && c.length < 160) {
      cand.push({ tag: e.tagName, cls: c, count: e.children.length });
    }
  });
  out.containers = cand.slice(0, 60);

  // 4) 是否存在分页
  out.pagination = {
    byClass: document.querySelectorAll('[class*=pagination]').length,
    byText: Array.from(document.querySelectorAll('*')).filter(e =>
      (e.innerText || '').trim() === '下一页').length,
  };

  // 5) body 纯文本前 800 字（确认是否在订单页）
  out.bodyText = (document.body ? document.body.innerText : '').slice(0, 800);
  return out;
}
"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(180000)
        page.goto(URL)
        print(">>> 请在浏览器里完成淘宝登录（扫码）。等待订单页出现…")
        # 等登录：出现“已买到的宝贝”文本即认为进入
        for _ in range(100):
            try:
                if page.query_selector("text=已买到的宝贝") or page.query_selector("text=导出订单"):
                    break
            except Exception:
                pass
            time.sleep(3)
        time.sleep(3)
        try:
            data = page.evaluate(PROBE_JS)
        except Exception as e:
            print("probe failed:", e)
            data = {}
        with open("probe_taobao_result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("=== ids ===");            print(data.get("ids"))
        print("=== textHits ===");       print(json.dumps(data.get("textHits"), ensure_ascii=False, indent=2))
        print("=== containers ===");     print(json.dumps(data.get("containers"), ensure_ascii=False, indent=2))
        print("=== pagination ===");     print(data.get("pagination"))
        print(">>> 结果已写入 probe_taobao_result.json")
        input(">>> 按回车关闭浏览器…")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
