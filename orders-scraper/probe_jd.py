# 京东新版订单页 DOM 探测脚本（临时诊断用）
# 用法：python probe_jd.py
# 目的：登录后 dump 订单容器/导出按钮/分页的真实 selector，
#       用于改写 jd.py 中可能已失效的旧版选择器（[id="order02"] 等）。
import time
import json
from playwright.sync_api import sync_playwright

URL = "https://order.jd.com/center/list.action"

PROBE_JS = r"""
() => {
  const out = {};
  out.url = location.href;
  out.title = document.title;

  // 1) 所有 id（前 80）
  out.ids = Array.from(document.querySelectorAll('[id]')).map(e => e.id).slice(0, 80);

  // 2) 含“导出/订单/宝贝/筛选/下一页”文本的可点元素
  const textHits = [];
  document.querySelectorAll('button, a, span, div[role=button]').forEach(e => {
    const t = (e.innerText || '').trim();
    if (t && t.length < 12 && /导出|下载|订单|筛选|上一页|下一页|批量/.test(t)) {
      textHits.push({ tag: e.tagName, text: t, cls: (e.className||'').toString().slice(0,120), id: e.id||null, href: e.getAttribute && e.getAttribute('href') });
    }
  });
  out.textHits = textHits.slice(0, 60);

  // 3) 疑似订单容器
  const cand = [];
  document.querySelectorAll('div, table, tbody, ul').forEach(e => {
    const c = (e.className||'').toString();
    if (/order|trade|item|list/i.test(c) && c.length < 160) {
      cand.push({ tag: e.tagName, id: e.id||null, cls: c, kids: e.children.length });
    }
  });
  out.containers = cand.slice(0, 60);

  // 4) 分页
  out.pagination = {
    byClass: document.querySelectorAll('[class*=pagination], .pagin, .next, .next-disabled').length,
    nextText: Array.from(document.querySelectorAll('*')).filter(e => (e.innerText||'').trim() === '下一页').length,
  };

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
        print(">>> 请在浏览器里完成京东登录（App/微信扫码，或账号密码）。等待订单页出现…")
        # 等登录：出现典型订单页文本即认为进入
        for _ in range(100):
            try:
                if (page.query_selector("text=我的订单")
                        or page.query_selector("text=订单号")
                        or page.query_selector("text=导出")
                        or page.query_selector('#order02')):
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
        with open("probe_jd_result.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("=== url/title ===");  print(data.get("url"), "|", data.get("title"))
        print("=== ids ===");        print(data.get("ids"))
        print("=== textHits ===");   print(json.dumps(data.get("textHits"), ensure_ascii=False, indent=2))
        print("=== containers ==="); print(json.dumps(data.get("containers"), ensure_ascii=False, indent=2))
        print("=== pagination ==="); print(data.get("pagination"))
        print(">>> 结果已写入 probe_jd_result.json")
        input(">>> 按回车关闭浏览器…")
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
