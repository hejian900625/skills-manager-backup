"""按真实日期区间查询移动「交费记录」（充值流水）。

页面默认日期为空 → 上一次等于没查。这里显式填起止日期再点查询。
登录态复用 数据结果/cmcc_session.json。
"""
import os
import re
import json

from playwright.sync_api import sync_playwright

BASE = r"C:\Users\Lenovo\数据结果"
SESSION = os.path.join(BASE, "cmcc_session.json")
OUT = os.path.join(BASE, "cmcc_probe")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 依次试的时间区间（由宽到窄），第一个有结果就停
RANGES = [
    ("2025-10-10", "2026-10-10", "近1年"),
    ("2026-05-10", "2026-10-10", "近5个月"),
]


def read_table(page):
    return page.evaluate("""() => {
        const tb = document.querySelector('#payHis-data');
        if (!tb) return null;
        if (tb.classList.contains('err')) return {empty: true};
        const rows = [];
        tb.querySelectorAll('tr').forEach(tr => {
            const tds = [...tr.querySelectorAll('td')].map(td => td.innerText.trim());
            if (tds.length >= 2 && tds[0]) rows.push(tds);
        });
        return {empty: rows.length === 0, rows: rows};
    }""")


def main():
    os.makedirs(OUT, exist_ok=True)
    result = {}
    with sync_playwright() as p:
        br = p.chromium.launch(headless=False,
                               args=["--disable-blink-features=AutomationControlled"])
        ctx = br.new_context(
            user_agent=UA, viewport={"width": 1440, "height": 900},
            storage_state=SESSION if os.path.exists(SESSION) else None)
        page = ctx.new_page()
        page.goto("https://shop.10086.cn/i/?f=recharhisqry", timeout=40000,
                  wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        txt = page.evaluate("() => (document.body?document.body.innerText:'')")
        print("登录态:", "已登录" if "退出" in txt else "**未登录**")
        if "退出" not in txt:
            print("需要重新登录，本次跳过")
            br.close()
            return

        for begin, end, tag in RANGES:
            print(f"\n--- 查询 {tag}：{begin} ~ {end} ---")
            page.evaluate("""([b, e]) => {
                const s = document.querySelector('#jf_start_time');
                const t = document.querySelector('#jf_end_time');
                if (s) { s.value = b; s.setAttribute('value', b); }
                if (t) { t.value = e; t.setAttribute('value', e); }
            }""", [begin, end])
            page.evaluate("() => { const b=document.querySelector('#query-btn'); if(b) b.click(); }")
            page.wait_for_timeout(5000)

            data = read_table(page)
            if data is None:
                print("  未找到结果表格")
                continue
            if data.get("empty"):
                print("  无交费记录")
                result[tag] = {"rows": 0}
                continue
            rows = data["rows"]
            print(f"  拿到 {len(rows)} 条：")
            for r in rows[:20]:
                print("   ", " | ".join(r))
            result[tag] = {"rows": len(rows), "data": rows}
            if rows:
                page.screenshot(path=os.path.join(OUT, "payrecord_filled.png"),
                                full_page=True)
                break

        ctx.storage_state(path=SESSION)
        br.close()

    with open(os.path.join(OUT, "payrecord_probe.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print("\n已写入 cmcc_probe/payrecord_probe.json")


if __name__ == "__main__":
    main()
