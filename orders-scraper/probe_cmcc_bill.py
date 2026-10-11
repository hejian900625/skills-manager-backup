# 探索中国移动账单页：月份控件 + 表格结构（读取渲染后的 DOM）
# 目的：搞清楚「逐月查账单」该怎么点、表格长什么样
import json
import os
import re

from playwright.sync_api import sync_playwright

SESSION = r"C:\Users\Lenovo\数据结果\cmcc_session.json"
OUT = r"C:\Users\Lenovo\数据结果\cmcc_probe"
os.makedirs(OUT, exist_ok=True)

URL = "https://shop.10086.cn/i/?f=billqry"

JS_DUMP = """() => {
  const out = {months: [], buttons: [], tables: [], text: ''};
  // 1) 所有疑似月份按钮
  document.querySelectorAll('a,button,li,span,div').forEach(e => {
    const t = (e.innerText || '').trim();
    if (!t || t.length > 30) return;
    if (/^\\d{4}[-年]\\d{1,2}$|^\\d{1,2}月$|^\\d{6}$/.test(t)) {
      out.months.push({tag: e.tagName, cls: (e.className||'').toString().slice(0,60),
                       id: e.id, txt: t});
    }
  });
  // 2) 可点击元素（查账单按钮）
  document.querySelectorAll('a,button').forEach(e => {
    const t = (e.innerText || '').trim();
    if (t && t.length <= 20) out.buttons.push({tag:e.tagName, id:e.id,
        cls:(e.className||'').toString().slice(0,60), txt:t});
  });
  // 3) 表格
  document.querySelectorAll('table').forEach(tb => {
    const rows = [];
    tb.querySelectorAll('tr').forEach(tr => {
      const c = [...tr.querySelectorAll('th,td')].map(x => (x.innerText||'').trim());
      if (c.length) rows.push(c.join(' | '));
    });
    if (rows.length) out.tables.push(rows);
  });
  out.text = (document.body ? document.body.innerText : '').slice(0, 3000);
  return out;
}"""


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"),
            viewport={"width": 1440, "height": 900},
            storage_state=SESSION if os.path.exists(SESSION) else None)
        page = ctx.new_page()
        page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        d = page.evaluate(JS_DUMP)
        print("=== 月份控件 ===")
        seen = set()
        for m in d["months"]:
            k = (m["txt"], m["cls"])
            if k in seen:
                continue
            seen.add(k)
            print(f"  {m['txt']:<12} tag={m['tag']} id={m['id']} cls={m['cls']}")
        print(f"\n=== 按钮（共 {len(d['buttons'])}） ===")
        seen = set()
        for b in d["buttons"]:
            if b["txt"] in seen:
                continue
            seen.add(b["txt"])
            print(f"  {b['txt']:<16} id={b['id']} cls={b['cls'][:40]}")
        print(f"\n=== 表格（{len(d['tables'])} 个） ===")
        for i, tb in enumerate(d["tables"]):
            print(f"  -- 表{i} {len(tb)}行 --")
            for r in tb[:15]:
                print("     ", r[:150])
        print("\n=== 正文 ===")
        print(re.sub(r"\s+", " ", d["text"])[:1500])

        # 尝试找页面里的查询函数（用于批量拉月份）
        fns = page.evaluate("""() => {
          const hits = [];
          for (const k of Object.keys(window)) {
            if (/bill|fee|qry|month/i.test(k)) {
              try { hits.push(k + ':' + typeof window[k]); } catch(e){}
            }
          }
          return hits.slice(0, 60);
        }""")
        print("\n=== window 上 bill/fee 相关 ===")
        print(" ", fns)

        page.screenshot(path=os.path.join(OUT, "bill_explore.png"), full_page=True)
        open(os.path.join(OUT, "bill_explore.html"), "w", encoding="utf-8").write(page.content())
        br.close()


if __name__ == "__main__":
    main()
