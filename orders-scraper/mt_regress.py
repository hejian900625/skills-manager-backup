# 美团订单解析「离线回归」——不联网、不烧真机。
# 回放：数据结果/mt_api/raw_*.json（接口翻页响应）+ 数据结果/mt_order_center.html（SSR 首屏），
# 重新走一遍 mt_export.py 的解析 → 补分类 → 写 CSV/XLSX。
# 用途：① 改解析逻辑后先在这里验证；② 不想再跑真机时用它重建交付文件。
#
# 跑法（必须在 C:/Users/Lenovo 下跑，因为输出目录是相对路径 数据结果/）：
#   cd "C:/Users/Lenovo" && C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe "C:/Users/Lenovo/.workbuddy/skills/orders_scraper/mt_regress.py"
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mt_export as M  # noqa: E402

DATA = r"C:\Users\Lenovo\数据结果"
APIDIR = os.path.join(DATA, "mt_api")
HTML = os.path.join(DATA, "mt_order_center.html")


def load_initial_state(path):
    """从保存下来的订单页 HTML 里抠出 window.__INITIAL_STATE__（括号配平）。"""
    if not os.path.exists(path):
        return None
    h = open(path, encoding="utf-8").read()
    i = h.find("__INITIAL_STATE__=")
    if i < 0:
        return None
    s = h.find("{", i)
    d = 0
    for j in range(s, len(h)):
        if h[j] == "{":
            d += 1
        elif h[j] == "}":
            d -= 1
            if d == 0:
                try:
                    return json.loads(h[s:j + 1])
                except Exception:
                    return None
    return None


def main():
    st = load_initial_state(HTML)
    if st:
        n = M.collect(st)
        print(f"SSR 首屏（{os.path.basename(HTML)}）：新增 {n}，累计 {len(M.ORDERS)}")
    else:
        print("!! 未找到或未能解析 SSR 首屏 HTML")

    files = sorted(glob.glob(os.path.join(APIDIR, "raw_*.json")))
    print(f"接口响应文件：{len(files)} 个")
    for f in files:
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        n = M.collect(d)
        page_n = M.PAGE_SIZES[-1] if M.PAGE_SIZES else 0
        if n:
            print(f"  {os.path.basename(f)}: 本页 {page_n} 条，新增 {n}，累计 {len(M.ORDERS)}")

    filled = M.fill_categories()
    print(f"分类补齐：{filled} 条 | 解析失败：{M.BAD_ROWS['n']} 条")
    rows = M.write_files()
    M.summary(rows)
    return len(rows)


if __name__ == "__main__":
    main()
