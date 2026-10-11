# 拼多多订单解析「离线回归」——不联网、不烧真机。
# 用已经抓到的接口原始响应（数据结果/pdd_api/raw_*.json）+ 首屏数据（数据结果/pdd_rawdata.json）
# 回放 pdd_export.py 的解析逻辑，验证能解析出多少订单、字段是否完整。
#
# 跑法：
#   C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe pdd_regress.py
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pdd_export as P  # noqa: E402

DATA = r"C:\Users\Lenovo\数据结果"
APIDIR = os.path.join(DATA, "pdd_api")
RAWDATA = os.path.join(DATA, "pdd_rawdata.json")


def feed(path, label):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    n = P.collect_orders(d)
    page_n = P.PAGE_SIZES[-1] if P.PAGE_SIZES else 0
    print(f"  {label}: 本页候选 {page_n} 条 → 新增 {n}，累计 {len(P.ORDERS)}")
    return n


def main():
    print("=== 回放接口响应（order_list_v4） ===")
    files = sorted(glob.glob(os.path.join(APIDIR, "raw_*.json")))
    for f in files:
        feed(f, os.path.basename(f))
    print(f"接口去重后累计: {len(P.ORDERS)} 条")

    if os.path.exists(RAWDATA):
        print("=== 回放首屏 rawData（ordersStore.orders） ===")
        feed(RAWDATA, "pdd_rawdata.json")

    rows = sorted(P.ORDERS.values(),
                  key=lambda r: r.get("下单时间") or "", reverse=True)
    print()
    print("=" * 62)
    print(f"总订单: {len(rows)} 条")
    years, status, total = {}, {}, 0.0
    empties = {"订单号": 0, "下单时间": 0, "实付金额": 0, "店铺": 0, "商品": 0}
    for r in rows:
        y = (r.get("下单时间") or "(无时间)")[:4]
        years[y] = years.get(y, 0) + 1
        s = r.get("订单状态") or "(无状态)"
        status[s] = status.get(s, 0) + 1
        try:
            total += float(r.get("实付金额") or 0)
        except Exception:
            pass
        for k in empties:
            if not r.get(k):
                empties[k] += 1
    print("年份分布:", "  ".join(f"{k}:{v}" for k, v in sorted(years.items(), reverse=True)))
    print("状态分布:", "  ".join(f"{k}:{v}" for k, v in status.items()))
    print(f"实付金额合计: ¥{total:.2f}")
    ts = [r["下单时间"] for r in rows if r.get("下单时间")]
    if ts:
        print("时间跨度:", min(ts)[:10], "~", max(ts)[:10])
    print("空字段计数:", empties)
    print("解析失败行数:", P.BAD_ROWS["n"], " 响应处理异常:", P.ERR_COUNT["n"])
    print("=" * 62)
    print("样例（前 5 条）:")
    for r in rows[:5]:
        print(f"  {r['订单号']} | {r['下单时间']} | {r['订单状态']} | "
              f"实付 {r['实付金额']} 应付 {r['应付金额']} 优惠 {r['优惠金额']} | "
              f"{r['店铺'][:14]} | {r['商品'][:32]}")
    return len(rows)


if __name__ == "__main__":
    main()
