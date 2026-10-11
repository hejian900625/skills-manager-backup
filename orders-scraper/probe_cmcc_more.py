# 移动「更早账单」最后一搏：重新登录 → 跑安全页面 → 谨慎试 1 个更早月份
#
# 背景：账单页月份列表前端硬编码 13 个；构造更早月份查询会触发风控（实测被踢登出）。
#      本脚本把风险操作放在最后，且只试 1 次，先拿到确定能拿的数据。
#
# 顺序：
#   1) 等登录（session 已失效，需短信随机码/服务密码/App 扫码）
#   2) 交费记录查询 ?f=recharhisqry  —— 充值流水，看能回溯多久
#   3) 我的账户 ?f=home              —— 余额/套餐
#   4) 账单页，只改一次 month 属性查 202509，验证「13 个月之外」是否真有数据
import json
import os
import re

from playwright.sync_api import sync_playwright

SESSION = r"C:\Users\Lenovo\数据结果\cmcc_session.json"
OUT = r"C:\Users\Lenovo\数据结果\cmcc_probe"
os.makedirs(OUT, exist_ok=True)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

JS_LOGGED = """() => {
  const t = (document.body ? document.body.innerText : '');
  if (t.length < 30) return false;
  if (/短信随机码|服务密码|请登录|立即登录/.test(t)) return false;
  return /退出|1\\d{2}\\*{4}\\d{4}|我的账户/.test(t);
}"""

JS_QRY_MONTH = """(m) => {
  const a = document.querySelector('#month13');
  if (!a) return 'no-btn';
  a.setAttribute('month', m);
  try { $(a).trigger('click'); } catch(e) { return 'err:' + e.message; }
  return 'ok';
}"""

JS_STATE = """() => {
  const nd = document.querySelector('#nodata');
  const box = document.querySelector('.zdcurmonth-comsum');
  const sumEl = document.querySelector('.zd-sum');
  const items = [...document.querySelectorAll('.zd-definite')].map(d => {
    const g = s => { const e = d.querySelector(s); return e ? e.innerText.trim() : ''; };
    return g('.zd-names') + '=' + (g('.zd-sjs') || g('.zd-ys'));
  });
  return {
    nodata: nd ? !nd.className.includes('none') : false,
    hidden: box ? box.className.includes('none') : true,
    sum: sumEl ? sumEl.innerText.trim() : '',
    items: items,
    month_tab: (document.querySelector('#month-tab') || {}).innerText || '',
  };
}"""

JS_PAY = """() => {
  const rows = [];
  document.querySelectorAll('table tr, .zd-list li, ul li').forEach(tr => {
    const t = (tr.innerText || '').replace(/\\s+/g, ' ').trim();
    if (t && /\\d{4}[-/年]\\d{1,2}[-/月]\\d{1,2}/.test(t) && t.length < 200) rows.push(t);
  });
  const sel = [...document.querySelectorAll('select')].map(s => ({
    id: s.id, opts: [...s.options].map(o => o.text).slice(0, 20)
  }));
  return {rows: rows.slice(0, 60), selects: sel,
          text: (document.body ? document.body.innerText : '').slice(0, 2500)};
}"""


def wait_login(page, limit=120):
    print(">>> 请在浏览器里登录中国移动（短信随机码 / 服务密码 / App 扫码）")
    for i in range(limit):
        page.wait_for_timeout(3000)
        if i % 5 == 0:
            print(f"    ...等待登录（{(i+1)*3}s）", flush=True)
        try:
            if page.evaluate(JS_LOGGED):
                return True
        except Exception:
            pass
    return False


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                             storage_state=SESSION if os.path.exists(SESSION) else None)
        page = ctx.new_page()

        print("=== 1) 账单页（兼登录） ===")
        page.goto("https://shop.10086.cn/i/?f=billqry", timeout=30000,
                  wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        if not page.evaluate(JS_LOGGED):
            if not wait_login(page):
                print("!! 登录超时")
                br.close()
                return
        print("  已登录")
        try:
            ctx.storage_state(path=SESSION)
            print("  session 已保存")
        except Exception:
            pass

        # ---- 2) 交费记录 ----
        print("\n=== 2) 交费记录查询 ?f=recharhisqry ===")
        try:
            page.goto("https://shop.10086.cn/i/?f=recharhisqry", timeout=25000,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(5000)
            d = page.evaluate(JS_PAY)
            print("  标题:", page.title())
            print("  可选下拉:", d["selects"])
            print(f"  含日期的行 {len(d['rows'])} 条，前 25：")
            for r in d["rows"][:25]:
                print("     ·", r[:130])
            print("  正文片段:", re.sub(r"\s+", " ", d["text"])[:700])
            open(os.path.join(OUT, "payrecord.html"), "w",
                 encoding="utf-8").write(page.content())
            page.screenshot(path=os.path.join(OUT, "payrecord.png"), full_page=True)
        except Exception as e:
            print("  失败:", type(e).__name__, e)

        # ---- 3) 账户 ----
        print("\n=== 3) 我的账户 ===")
        try:
            page.goto("https://shop.10086.cn/i/?f=home", timeout=25000,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            t = page.evaluate("() => (document.body?document.body.innerText:'')")
            for k in ["可用余额", "账户总余额", "当前套餐", "上月消费", "平均每月消费"]:
                m = re.search(k + r"[:：]?\s*([^\n]{0,25})", t)
                print(f"  {k}: {m.group(1).strip() if m else '-'}")
        except Exception as e:
            print("  失败:", type(e).__name__, e)

        # ---- 4) 谨慎试 1 个更早月份 ----
        print("\n=== 4) 试查 202509（13 个月之外，只试 1 次） ===")
        try:
            page.goto("https://shop.10086.cn/i/?f=billqry", timeout=25000,
                      wait_until="domcontentloaded")
            page.wait_for_timeout(6000)
            if not page.evaluate(JS_LOGGED):
                print("  !! 回到账单页已掉登录态 —— 停止（前面触发的风控未解除）")
                br.close()
                return
            n_before = page.evaluate("() => document.querySelectorAll('a[id^=month]').length")
            print("  月份按钮数:", n_before)
            # 先记录当前 2025-10（末尾月）的值做对照
            r = page.evaluate(JS_QRY_MONTH, "202510")
            page.wait_for_timeout(3500)
            s0 = page.evaluate(JS_STATE)
            print(f"  对照 202510 -> sum={s0['sum']} items={s0['items']}")
            # 再查 202509
            r = page.evaluate(JS_QRY_MONTH, "202509")
            print("  trigger:", r)
            page.wait_for_timeout(4000)
            s1 = page.evaluate(JS_STATE)
            print(f"  202509   -> nodata={s1['nodata']} sum={s1['sum']} items={s1['items']}")
            print("  月份标签:", s1.get("month_tab", "")[:40])
            # 登录态是否还在
            ok = page.evaluate(JS_LOGGED)
            print("  查询后登录态:", "仍在" if ok else "已被踢出")
            json.dump({"base_202510": s0, "probe_202509": s1, "still_login": ok},
                      open(os.path.join(OUT, "older_probe.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        except Exception as e:
            print("  失败:", type(e).__name__, e)

        try:
            ctx.storage_state(path=SESSION)
        except Exception:
            pass
        br.close()


if __name__ == "__main__":
    main()
