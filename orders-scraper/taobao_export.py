# 淘宝订单导出（新版页面，基于「导出订单」按钮 + 下载捕获）
# 由 orders_scraper/taobao.py 重写而来；旧版 #bought / rc-calendar 选择器已废弃。
import time
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

URL = "https://buyertrade.taobao.com/trade/itemlist/list_bought_items.htm"
OUT_DIR = "数据结果"                      # 调试日志等（本脚本只捕获下载，无其它调试产物）
# 订单下载落点：直接进个人站数据管线的 orders 目录，免去手动 copy（可用环境变量 ORDERS_DIR 覆盖）
ORDERS_DIR = os.environ.get("ORDERS_DIR", r"D:\site_sources\orders")

# 候选选择器（探测结果回来后可校准；按顺序尝试）
EXPORT_BTN_CANDIDATES = [
    "text=导出订单",
    "button:has-text('导出订单')",
    "a:has-text('导出订单')",
]

# 登录成功判据（出现任一即可）
LOGGED_IN_MARKERS = ["text=已买到的宝贝", "text=导出订单", "text=我的订单"]


def wait_login(page, timeout_s=300):
    waited = 0
    while waited < timeout_s:
        for m in LOGGED_IN_MARKERS:
            try:
                if page.query_selector(m):
                    return True
            except Exception:
                pass
        time.sleep(3)
        waited += 3
    return False


def find_export_button(page):
    for sel in EXPORT_BTN_CANDIDATES:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return loc, sel
        except Exception:
            continue
    return None, None


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(180000)

        page.goto(URL)
        print(">>> 请扫码登录淘宝（最多等 5 分钟）…")
        if not wait_login(page):
            print("!! 登录未完成或页面改版，退出。")
            context.close(); browser.close(); return
        print(">>> 已进入订单页")
        time.sleep(2)

        btn, used = find_export_button(page)
        if btn is None:
            print("!! 没找到「导出订单」按钮，可能页面改版。请跑 probe_taobao.py 看 DOM。")
            context.close(); browser.close(); return
        print(">>> 找到导出按钮，选择器:", used)

        # 点导出并捕获下载
        try:
            with page.expect_download(timeout=120000) as dl_info:
                btn.click()
            download = dl_info.value
            suggested = download.suggested_filename or f"taobao_orders_{datetime.now():%Y-%m-%d}.csv"
            os.makedirs(ORDERS_DIR, exist_ok=True)
            save_path = os.path.join(ORDERS_DIR, suggested)
            download.save_as(save_path)
            print(">>> 已下载:", save_path)
            if not suggested.lower().endswith((".xlsx", ".csv")):
                print("!! 警告：淘宝导出为 %s，fetch_shopping 目前只吃 .xlsx/.csv；"
                      "若为 .xls 请在 Excel 里「另存为 .xlsx」后再跑数据管线。" % suggested)
        except Exception as e:
            print("!! 点击导出后未捕获到下载。可能弹了日期范围框或跳转，错误:", e)
            print(">>> 保持浏览器打开 60s 供你观察…")
            time.sleep(60)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
