# 探测：中国移动账单「13 个月之前」到底还有没有数据
# 原理：账单页月份列表是前端硬编码生成 13 个（for(var i=0;13>i;i++)），
#       但点击处理只读 <a> 的 month 属性：var a=$(this).attr("month"); return S(a)
#       → 改掉现有按钮的 month 属性再 trigger('click')，即可查询任意月份。
import os
import re

from playwright.sync_api import sync_playwright

SESSION = r"C:\Users\Lenovo\数据结果\cmcc_session.json"
OUT = r"C:\Users\Lenovo\数据结果\cmcc_probe"
os.makedirs(OUT, exist_ok=True)
URL = "https://shop.10086.cn/i/?f=billqry"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 先用稀疏采样找边界，再决定要不要逐月全量
PROBE_MONTHS = ["202509", "202508", "202506", "202503", "202501",
                "202412", "202409", "202406", "202403", "202312",
                "202306", "202301", "202206", "202106", "202006"]

JS_QRY = """(m) => {
  const a = document.querySelector('#month13');
  if (!a) return 'no-btn';
  a.setAttribute('month', m);
  try { $(a).trigger('click'); } catch(e) { return 'err:' + e.message; }
  return 'ok';
}"""

JS_STATE = """() => {
  const nd = document.querySelector('#nodata');
  const box = document.querySelector('.zdcurmonth-comsum');
  const nodata = nd ? !nd.className.includes('none') : false;
  const hidden = box ? box.className.includes('none') : true;
  const sumEl = document.querySelector('.zd-sum');
  const items = document.querySelectorAll('.zd-definite').length;
  return {nodata: nodata, hidden: hidden,
          sum: sumEl ? sumEl.innerText.trim() : '', items: items,
          text: (document.body ? document.body.innerText : '').slice(0, 260)};
}"""


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                             storage_state=SESSION if os.path.exists(SESSION) else None)
        page = ctx.new_page()
        page.goto(URL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
        if page.evaluate("() => /短信随机码|服务密码/.test(document.body.innerText)"):
            print("!! 登录态失效")
            br.close()
            return

        print(f"{'月份':<8} {'状态':<8} {'总额':>10} {'分项':>4}  备注")
        print("-" * 68)
        last_ok = None
        for m in PROBE_MONTHS:
            r = page.evaluate(JS_QRY, m)
            if r != "ok":
                print(f"{m:<8} {r}")
                continue
            page.wait_for_timeout(3000)
            s = page.evaluate(JS_STATE)
            if s["nodata"] or s["hidden"] or not s["items"]:
                status = "无数据"
                print(f"{m:<8} {'无数据':<8} {'-':>10} {'0':>4}  "
                      + re.sub(r"\s+", " ", s["text"])[:40])
            else:
                status = "有数据"
                last_ok = m
                print(f"{m:<8} {'有数据':<8} {s['sum']:>10} {s['items']:>4}")
            page.wait_for_timeout(800)
        print("-" * 68)
        print("最早有数据的采样月份:", last_ok or "无（13 个月之外都没有）")
        br.close()


if __name__ == "__main__":
    main()
