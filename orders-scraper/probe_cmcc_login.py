# 中国移动「话费账单/详单」登录取证
# 目的：登录后回答
#   1. 月账单页有哪些字段？从哪个接口来？
#   2. 通话/短信/流量详单能不能拿？（注意：移动详单通常要短信二次验证）
#   3. 能不能批量导出历史多月账单？
#
# 用法：python probe_cmcc_login.py
# 产出：数据结果/cmcc_session.json、cmcc_probe/*.html|png、cmcc_api/*.json
import json
import os
import re
from playwright.sync_api import sync_playwright

OUT = r"C:\Users\Lenovo\数据结果\cmcc_probe"
API = r"C:\Users\Lenovo\数据结果\cmcc_api"
SESSION = r"C:\Users\Lenovo\数据结果\cmcc_session.json"
os.makedirs(OUT, exist_ok=True)
os.makedirs(API, exist_ok=True)

START = "https://shop.10086.cn/i/?f=billqry"      # 账单查询
PAGES = [
    ("bill", "https://shop.10086.cn/i/?f=billqry"),
    ("detail", "https://shop.10086.cn/i/?f=billdetailqry"),
    ("home", "https://shop.10086.cn/i/?f=home"),
    ("remain", "https://shop.10086.cn/i/?f=packremainqry"),
]
API_KEY = re.compile(r"(bill|qry|fee|detail|account|balance|call|sms|gprs|flow|invoice)", re.I)
captured = []


def on_resp(resp):
    try:
        u = resp.url
        if not API_KEY.search(u) or "10086.cn" not in u:
            return
        body = ""
        try:
            ct = (resp.headers or {}).get("content-type", "")
            if "json" in ct or "javascript" in ct or "text" in ct:
                body = resp.text()[:300000]
        except Exception:
            pass
        captured.append((resp.status, u, len(body)))
        if body:
            json.dump({"url": u, "status": resp.status, "body": body},
                      open(os.path.join(API, f"c_{len(captured):02d}.json"), "w",
                           encoding="utf-8"), ensure_ascii=False)
        print(f"  [API {len(captured):>2}] {resp.status} {u[:130]} ({len(body)}B)")
    except Exception:
        pass


def logged_in(page):
    """判据：出现手机号掩码 / 退出登录 / 账单内容，且不在登录页。

    沿用高德的教训：不要拿匿名就有的 cookie/localStorage 键当凭据。
    """
    try:
        txt = page.evaluate("() => (document.body?document.body.innerText:'')")
    except Exception:
        return False
    if len(txt) < 30:
        return False
    # 还在登录页
    if re.search(r"(短信随机码|服务密码|请登录|立即登录|扫码登录|短信登录|密码登录)", txt):
        return False
    # 登录后才有的特征
    if re.search(r"(退出|退出登录|1\d{2}\*{4}\d{4}|尊敬的|我的账户)", txt):
        return True
    return False


def dump(page, name):
    try:
        page.wait_for_timeout(3500)
    except Exception:
        pass
    try:
        open(os.path.join(OUT, name + ".html"), "w", encoding="utf-8").write(page.content())
    except Exception:
        pass
    try:
        page.screenshot(path=os.path.join(OUT, name + ".png"), full_page=False)
    except Exception:
        pass
    txt = page.evaluate("() => (document.body?document.body.innerText:'')")
    print(f"\n===== {name} =====")
    print(f"  url  : {page.url}")
    print(f"  title: {page.title()}")
    print(f"  正文 {len(txt)} 字")
    print("  正文片段: " + re.sub(r"\s+", " ", txt)[:600])
    # 尝试抓表格
    try:
        rows = page.evaluate("""() => { const o=[];
            document.querySelectorAll('table tr').forEach(tr=>{
              const c=[...tr.querySelectorAll('th,td')].map(t=>(t.innerText||'').trim());
              if(c.length) o.push(c.join(' | '));});
            return o.slice(0,40); }""")
        if rows:
            print(f"  表格 {len(rows)} 行：")
            for r in rows[:20]:
                print("     ·", r[:160])
    except Exception:
        pass


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
        page.on("response", on_resp)

        page.goto(START, timeout=30000, wait_until="domcontentloaded")
        if not logged_in(page):
            print("\n>>> 请在浏览器里登录中国移动（短信随机码 / 服务密码 / App 扫码）")
            print(">>> 登录成功后脚本自动继续；若查详单要二次验证码，也请在页面上完成。\n")
            for i in range(120):          # 最多 6 分钟
                page.wait_for_timeout(3000)
                if i % 5 == 0:
                    print(f"    ...等待登录（{(i+1)*3}s）", flush=True)
                if logged_in(page):
                    break
        print(f"\n登录态: {'已登录' if logged_in(page) else '未登录（匿名继续）'}")
        try:
            ctx.storage_state(path=SESSION)
            print("  已保存登录态 ->", SESSION)
        except Exception as e:
            print("  保存失败:", e)

        for name, u in PAGES:
            try:
                page.goto(u, timeout=25000, wait_until="domcontentloaded")
                dump(page, name)
            except Exception as e:
                print(f"  [ERR] {u}: {type(e).__name__}: {e}")
        print(f"\n===== 汇总：捕获接口 {len(captured)} 条，写入 {API} =====")
        br.close()


if __name__ == "__main__":
    main()
