# 中国移动「近 13 个月话费账单」导出
# 数据源：PC 网上营业厅账单页（shop.10086.cn/i/?f=billqry）
#   接口响应是 AES 密文（outParam），无法直接解析 → 走「页面渲染后取 DOM」
#   月份按钮：<a id="monthN" month="YYYYMM">，共 13 个月
#   账单容器：#curmonth-comsum（分项在 .zd-list-items / .zd-definite）
#
# 用法：python cmcc_export.py
# 产出：数据结果/cmcc_bills_YYYY-MM-DD.xlsx / .csv / cmcc_bill_raw/*.html
import csv
import datetime as dt
import os
import re

from playwright.sync_api import sync_playwright

SESSION = r"C:\Users\Lenovo\数据结果\cmcc_session.json"
OUTDIR = r"C:\Users\Lenovo\数据结果"
RAW = os.path.join(OUTDIR, "cmcc_bill_raw")
os.makedirs(RAW, exist_ok=True)

URL_BILL = "https://shop.10086.cn/i/?f=billqry"
URL_HOME = "https://shop.10086.cn/i/?f=home"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

MONTHS = []          # [(month_attr, label)]
BILLS = {}           # month -> {sum, period, items[], total{}}
ACCOUNT = {}


def num(s):
    """'2.00' -> 2.0；空/异常 -> ''"""
    s = (s or "").strip().replace(",", "")
    if not s:
        return ""
    try:
        return round(float(s), 2)
    except Exception:
        return ""


JS_LIST_MONTHS = """() => {
  const out = [];
  document.querySelectorAll('a[id^=month]').forEach(a => {
    const m = a.getAttribute('month');
    const t = (a.innerText || '').trim();
    if (m && t) out.push([m, t, a.id]);
  });
  return out;
}"""

JS_READ_BILL = """() => {
  const root = document.querySelector('#curmonth-comsum');
  if (!root) return null;
  const txt = el => el ? (el.innerText || '').trim() : '';
  const periodEl = [...document.querySelectorAll('*')]
      .find(e => /计费周期/.test(e.innerText || '') && (e.innerText||'').length < 80);
  const items = [];
  root.querySelectorAll('.zd-list-items').forEach(li => {
    const cat = txt(li.querySelector('.zditem-title'));
    li.querySelectorAll('.zd-definite').forEach(d => {
      items.push({
        cat: cat,
        name: txt(d.querySelector('.zd-names')),
        ys:   txt(d.querySelector('.zd-ys')),
        jms:  txt(d.querySelector('.zd-jms')),
        sjs:  txt(d.querySelector('.zd-sjs')),
      });
    });
  });
  const hj = root.querySelector('.zd-summation');
  return {
    sum: txt(root.querySelector('.zd-sum')),
    name: txt(root.querySelector('.zd-name')),
    phone: txt(root.querySelector('.zd-num')),
    star: txt(root.querySelector('.zd-star')),
    period: periodEl ? periodEl.innerText.replace(/\\s+/g, ' ').trim() : '',
    items: items,
    total: {
      ys:  hj ? txt(hj.querySelector('.zd-hjs.zd-ys'))  : '',
      jms: hj ? txt(hj.querySelector('.zd-hjs.zd-jms')) : '',
      sjs: hj ? txt(hj.querySelector('.zd-hjs.zd-sjs')) : '',
    }
  };
}"""

JS_ACCOUNT = """() => {
  const t = (document.body ? document.body.innerText : '');
  const g = re => { const m = t.match(re); return m ? m[1].trim() : ''; };
  return {
    balance: g(/可用余额[:：]\\s*([\\d.]+)\\s*元/),
    total_balance: g(/账户总余额\\s*[:：]\\s*([\\d.]+)\\s*元/),
    month_fee: g(/当月消费\\s*[:：]\\s*([\\d.]+)\\s*元/),
    plan: g(/当前套餐[:：]\\s*([^\\n]+)/),
    star: g(/星级[:：]\\s*([^\\n]+)/),
    last_month: g(/上月消费[:：]\\s*([\\d.]+)元/),
    avg_month: g(/平均每月消费[:：]\\s*([\\d.]+)元/),
  };
}"""


def read_month(page, idx, mid, label):
    """点击某个月份按钮并读取账单。返回 True/False"""
    try:
        if idx > 0:
            # 月份列表是折叠下拉，Playwright 的 click 会因 not visible 超时
            # → 用页面内 JS 直接触发（绕过可点击性检查）
            ok = page.evaluate("""(mid) => {
                const a = document.getElementById(mid);
                if (!a) return false;
                a.click();
                return true;
            }""", mid)
            if not ok:
                print(f"   [{label}] 找不到按钮 #{mid}")
                return False
        page.wait_for_timeout(2500)
        d = page.evaluate(JS_READ_BILL)
        if not d or not d.get("items"):
            # 再等等（异步渲染）
            page.wait_for_timeout(2500)
            d = page.evaluate(JS_READ_BILL)
        if not d:
            print(f"   [{label}] 未取到账单容器")
            return False
        BILLS[label] = d
        n = len(d.get("items") or [])
        print(f"   [{label}] 总消费 {d.get('sum') or '-'} 元，"
              f"分项 {n} 条，周期 {d.get('period', '')[:24]}")
        try:
            open(os.path.join(RAW, f"bill_{label}.html"), "w",
                 encoding="utf-8").write(page.content())
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"   [{label}] 失败: {type(e).__name__}: {e}")
        return False


def write_files():
    stamp = dt.date.today().isoformat()
    # ---- 明细表 ----
    det_fields = ["账单月份", "计费周期", "消费大类", "明细项目",
                  "原价(元)", "减免(元)", "实际消费(元)"]
    det = []
    # ---- 汇总表 ----
    sum_fields = ["账单月份", "计费周期", "账单总额(元)", "原价合计(元)",
                  "减免合计(元)", "实际消费合计(元)", "分项数"]
    sm = []
    for label in sorted(BILLS, reverse=True):
        d = BILLS[label]
        period = re.sub(r"^计费周期[:：]?\s*", "", d.get("period", "")).strip()
        t = d.get("total") or {}
        sm.append({
            "账单月份": label,
            "计费周期": period,
            "账单总额(元)": num(d.get("sum")),
            "原价合计(元)": num(t.get("ys")),
            "减免合计(元)": num(t.get("jms")),
            "实际消费合计(元)": num(t.get("sjs")),
            "分项数": len(d.get("items") or []),
        })
        for it in (d.get("items") or []):
            det.append({
                "账单月份": label,
                "计费周期": period,
                "消费大类": it.get("cat", ""),
                "明细项目": it.get("name", ""),
                "原价(元)": num(it.get("ys")),
                "减免(元)": num(it.get("jms")),
                "实际消费(元)": num(it.get("sjs")),
            })

    def dump(name, fields, rows):
        p = os.path.join(OUTDIR, f"{name}_{stamp}.csv")
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(fields)
            for r in rows:
                ws.append([r[k] for k in fields])
            for i, k in enumerate(fields, 1):
                ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = \
                    max(12, min(30, len(k) * 2 + 4))
            wb.save(os.path.join(OUTDIR, f"{name}_{stamp}.xlsx"))
        except Exception as e:
            print("  (xlsx 写出跳过:", e, ")")
        return p

    p1 = dump("cmcc_bills", sum_fields, sm)
    p2 = dump("cmcc_bill_items", det_fields, det)
    print(f"\n[OUT] 月度汇总 -> {p1}")
    print(f"[OUT] 分项明细 -> {p2}")
    return p1, p2


def main():
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                             storage_state=SESSION if os.path.exists(SESSION) else None)
        page = ctx.new_page()

        print("=== 打开账单页 ===")
        page.goto(URL_BILL, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        if "登录" in page.title() or page.evaluate(
                "() => /短信随机码|服务密码/.test(document.body.innerText)"):
            print("!! 登录态失效，请重新登录（删除 cmcc_session.json 后重跑探测脚本）")
            br.close()
            return

        lst = page.evaluate(JS_LIST_MONTHS)
        if not lst:
            print("!! 未找到月份按钮（页面结构可能变了）")
            br.close()
            return
        print(f"发现 {len(lst)} 个月份按钮")
        for i, (m, label, mid) in enumerate(lst):
            read_month(page, i, mid, label)

        print("\n=== 账户概览 ===")
        try:
            page.goto(URL_HOME, timeout=25000, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            ACCOUNT.update(page.evaluate(JS_ACCOUNT))
            print("  ", ACCOUNT)
        except Exception as e:
            print("  账户页失败:", type(e).__name__, e)

        try:
            ctx.storage_state(path=SESSION)
        except Exception:
            pass
        br.close()

    write_files()
    # 打印汇总
    print("\n===== 月度账单汇总 =====")
    for label in sorted(BILLS, reverse=True):
        d = BILLS[label]
        t = d.get("total") or {}
        print(f"  {label}  实际消费 {t.get('sjs') or d.get('sum') or '-':>8} 元"
              f"  (原价 {t.get('ys', '-')} / 减免 {t.get('jms', '-')})"
              f"  分项 {len(d.get('items') or [])}")
    if ACCOUNT:
        print("\n===== 账户 =====")
        print(f"  可用余额 {ACCOUNT.get('balance')} 元 | 当月消费 {ACCOUNT.get('month_fee')} 元"
              f" | 上月 {ACCOUNT.get('last_month')} 元 | 月均 {ACCOUNT.get('avg_month')} 元")
        print(f"  套餐：{ACCOUNT.get('plan')}")


if __name__ == "__main__":
    main()
