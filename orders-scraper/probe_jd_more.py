# 京东订单页「更多」按钮定位探测（定向，第五段）
# 背景：probe_jd_page.py 已证明"点更多"能触发第 2 页请求；但 jd_export.py v4 的
#       过滤条件（叶子节点 + 非订单卡内）没能点到它 → 需要逐个候选点一遍，看谁生效。
# 本脚本：
#   A. 切到「2022年订单」（totalNum=81，必须翻页）
#   B. 枚举**所有**文本为 更多/加载更多/查看更多/下一页 的元素，输出：tag/class/是否在订单卡内/
#      子节点数/坐标/是否可见/4 层祖先链
#   C. 从最靠下的候选开始，**逐个**用鼠标点，每次点完等 3.5s，记录 API 请求数与 postData 是否出现 page=2
#      （点完按 Esc + 点空白处关闭可能弹出的菜单）
#   D. 顺带：把时间下拉**内部滚动到底**，读出全部选项（v3/v4 只读到 11 个，缺 2015/2014/2014前）
# 产物：probe_jd_more.json + 数据结果/probe5_after.png
import os
import json
import time
import traceback
from playwright.sync_api import sync_playwright

URL = "https://order.jd.com/center/list.action"
OUT_DIR = "数据结果"
STATE = os.path.join(OUT_DIR, "jd_session.json")
LOGIN_MARKERS = ["text=订单中心", "text=我的订单", "#orderLite", "[class*='orderCard-']"]
TARGET_RANGE = "2022年订单"
MORE_TEXTS = ["下一页", "加载更多", "查看更多", "更多", "展开更多"]

AUTH_COOKIE_NAMES = ("pt_key", "pin")

ENUM_JS = r"""
(texts) => {
  const cards = Array.from(document.querySelectorAll('[class*="orderCard-"]'));
  const inCard = (el) => cards.some(c => c.contains(el));
  const chain = (el) => {
    const out = []; let e = el;
    for (let i = 0; i < 5 && e; i++) {
      out.push(e.tagName + '.' + ((e.className || '').toString().slice(0, 60)));
      e = e.parentElement;
    }
    return out;
  };
  const out = [];
  document.querySelectorAll('*').forEach(e => {
    const t = (e.innerText || '').trim();
    if (!texts.includes(t)) return;
    const r = e.getBoundingClientRect();
    out.push({
      tag: e.tagName, cls: (e.className || '').toString().slice(0, 90), text: t,
      children: e.children.length, inCard: inCard(e),
      x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2),
      w: Math.round(r.width), h: Math.round(r.height),
      visible: r.width > 0 && r.height > 0,
      chain: chain(e)
    });
  });
  out.sort((a, b) => {
    const pa = texts.indexOf(a.text), pb = texts.indexOf(b.text);
    if (pa !== pb) return pa - pb;      // 「下一页」优先
    return b.y - a.y;                   // 同优先级取最靠下
  });
  return out;
}
"""


def has_login_cookie(context):
    try:
        names = {c.get("name") for c in context.cookies()}
        for n in AUTH_COOKIE_NAMES:
            if n in names:
                return True
    except Exception:
        pass
    return False


def ensure_logged_in(context, page, timeout_s=300):
    print(f">>> 检查登录态（最多等 {timeout_s} 秒；已登录会立即通过）…")
    deadline = time.time() + timeout_s
    waited = 0
    last = -1
    while time.time() < deadline:
        if has_login_cookie(context):
            print(">>> 已登录（pt_key/pin）")
            break
        if waited // 5 != last:
            last = waited // 5
            try:
                url = page.url
            except Exception:
                url = "(取不到)"
            print(f"    [{waited}s] URL={url[:90]}")
        try:
            if "passport.jd.com" not in page.url and "login" not in page.url.lower():
                for m in LOGIN_MARKERS:
                    if page.query_selector(m):
                        print(">>> 页面已是订单页")
                        return True
        except Exception:
            pass
        time.sleep(2)
        waited += 2
    else:
        print("!! 超时未登录")
        return False
    for _ in range(3):
        try:
            page.goto(URL, wait_until="domcontentloaded"); break
        except Exception:
            time.sleep(2)
    time.sleep(4)
    print(">>> 当前 URL:", page.url)
    return True


def read_time_options_full(page, rounds=8):
    """点开时间下拉后，把下拉列表内部滚到底，读完所有选项（避免只读到可视区前 11 个）。"""
    try:
        page.evaluate("""() => {
            const el = document.querySelector('[class*="selectList-"]');
            if (el) el.scrollTop = 0;
        }""")
    except Exception:
        pass
    seen = []
    for _ in range(rounds):
        try:
            vals = page.eval_on_selector_all(
                '[class*="selectList-"] [class*="item-"]',
                "els=>els.map(e=>(e.innerText||'').trim()).filter(Boolean)")
        except Exception:
            vals = []
        for v in vals:
            if v not in seen:
                seen.append(v)
        try:
            moved = page.evaluate("""() => {
                const el = document.querySelector('[class*="selectList-"]');
                if (!el) return false;
                const before = el.scrollTop;
                el.scrollTop = Math.min(el.scrollTop + el.clientHeight * 0.8, el.scrollHeight);
                return el.scrollTop > before;
            }""")
        except Exception:
            moved = False
        time.sleep(0.5)
        if not moved:
            break
    return seen


def open_dropdown(page):
    try:
        el = page.query_selector('[class*="selectContainer-"]')
        if not el:
            return []
        box = el.bounding_box()
        if not box:
            return []
        page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        time.sleep(1.6)
        return read_time_options_full(page)
    except Exception:
        return []


def click_option(page, text):
    try:
        pos = page.evaluate("""(t) => {
            const els = document.querySelectorAll('[class*="selectList-"] [class*="item-"]');
            for (const e of els) {
                if ((e.innerText || '').trim() === t) {
                    e.scrollIntoView({block: 'center'});
                    const r = e.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }
            }
            return null;
        }""", text)
        if not pos:
            return False
        page.mouse.click(pos["x"], pos["y"])
        return True
    except Exception:
        return False


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        have = os.path.exists(STATE)
        context = browser.new_context(storage_state=STATE) if have else browser.new_context()
        page = context.new_page()
        page.set_default_timeout(180000)

        reqs = []

        def on_request(r):
            try:
                if "api.m.jd.com" in r.url and "functioncode=pcorder_center_list" in r.url.lower():
                    reqs.append(r.post_data)
            except Exception:
                pass
        page.on("request", on_request)

        try:
            page.goto(URL, wait_until="domcontentloaded")
        except Exception:
            pass
        if not ensure_logged_in(context, page, 300):
            try:
                context.close(); browser.close()
            except Exception:
                pass
            return
        try:
            context.storage_state(path=STATE)
        except Exception:
            pass
        try:
            page.evaluate("""() => document.querySelectorAll('[class*="tooltipFilter-"]').forEach(e=>e.remove())""")
        except Exception:
            pass
        time.sleep(1)

        # ---- D. 完整读时间下拉选项 ----
        opts = open_dropdown(page)
        print(">>> 时间下拉**全量**选项:", opts)

        # ---- A. 切到目标范围 ----
        if TARGET_RANGE in opts:
            click_option(page, TARGET_RANGE)
            print(f">>> 已切换到 {TARGET_RANGE}")
        else:
            print(f"!! 未找到 {TARGET_RANGE}")
        time.sleep(4.5)

        report = {"target": TARGET_RANGE, "time_options": opts, "cands": [], "clicks": [],
                  "base_reqs": list(reqs)}

        # ---- B. 枚举所有「更多」候选 ----
        cands = page.evaluate(ENUM_JS, MORE_TEXTS)
        report["cands"] = cands
        print(f"\n=== 找到 {len(cands)} 个「更多」类候选 ===")
        for i, c in enumerate(cands):
            print(f"  [{i}] {c['tag']}.{c['cls'][:38]} text={c['text']!r} inCard={c['inCard']} "
                  f"children={c['children']} @({c['x']},{c['y']}) vis={c['visible']}")
            print(f"      chain: {' < '.join(c['chain'][:4])}")

        # ---- C. 逐个点，看谁触发 page=2 ----
        print(f"\n=== 逐个点击候选，观察 API 请求 ===")
        for i, c in enumerate(cands):
            if not c["visible"]:
                report["clicks"].append({"i": i, "skipped": "not visible"})
                continue
            n_before = len(reqs)
            try:
                page.keyboard.press("Escape")
                time.sleep(0.3)
                # 滚到该元素再取最新坐标
                pos = page.evaluate("""(arg) => {
                    const texts = arg.texts, i = arg.i;
                    const cards = Array.from(document.querySelectorAll('[class*="orderCard-"]'));
                    const inCard = (el) => cards.some(c => c.contains(el));
                    const out = [];
                    document.querySelectorAll('*').forEach(e => {
                        const t = (e.innerText||'').trim();
                        if (!texts.includes(t)) return;
                        const r = e.getBoundingClientRect();
                        out.push({el: e, t: t, y: r.y, inCard: inCard(e), vis: r.width>0&&r.height>0});
                    });
                    out.sort((a,b) => {
                        const pa = texts.indexOf(a.t), pb = texts.indexOf(b.t);
                        if (pa !== pb) return pa - pb;
                        return b.y - a.y;
                    });
                    if (i >= out.length) return null;
                    const e = out[i].el;
                    e.scrollIntoView({block:'center'});
                    const r = e.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2, inCard: out[i].inCard, t: out[i].t};
                }""", {"texts": MORE_TEXTS, "i": i})
                if not pos:
                    report["clicks"].append({"i": i, "skipped": "no pos"})
                    continue
                time.sleep(0.8)
                page.mouse.click(pos["x"], pos["y"])
                time.sleep(3.5)
                n_after = len(reqs)
                rec = {"i": i, "text": pos.get("t"), "cls": c["cls"][:60], "inCard": pos.get("inCard"),
                       "reqs_before": n_before, "reqs_after": n_after,
                       "new_reqs": reqs[n_before:n_after]}
                report["clicks"].append(rec)
                print(f"  [{i}] click text={pos.get('t')!r} cls={c['cls'][:30]} inCard={pos.get('inCard')} "
                      f"reqs {n_before}→{n_after} new={reqs[n_before:n_after]}")
                # 关掉可能弹出的菜单
                page.keyboard.press("Escape")
                try:
                    page.mouse.click(700, 60)
                except Exception:
                    pass
                time.sleep(0.8)
                if n_after > n_before and any(x for x in reqs[n_before:n_after]):
                    print(f"  ✅ 命中！候选 [{i}]（text={pos.get('t')!r}）触发了新请求")
                    break
            except Exception as e:
                report["clicks"].append({"i": i, "error": f"{type(e).__name__}: {str(e)[:120]}"})
                print(f"  [{i}] 点击异常: {type(e).__name__}: {str(e)[:100]}")

        # ---- C2. Playwright 定位器点击（probe_jd_page.py 里唯一成功触发 page=2 的方式）----
        print("\n=== Playwright 定位器逐一点击（带可点击性检查 + 自动滚动）===")
        for label in ("下一页", "加载更多", "查看更多"):
            try:
                loc = page.locator('text="%s"' % label)
                n = loc.count()
            except Exception:
                n = 0
            print(f"  「{label}」匹配 {n} 个")
            for i in range(min(n, 4)):
                n0 = len(reqs)
                ok = False
                try:
                    loc.nth(i).scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                try:
                    loc.nth(i).click(timeout=4000)
                    ok = True
                except Exception as e:
                    try:
                        box = loc.nth(i).bounding_box()
                        if box:
                            page.mouse.click(box["x"] + box["width"] / 2,
                                             box["y"] + box["height"] / 2)
                            ok = True
                    except Exception:
                        pass
                    if not ok:
                        print(f"    点击异常: {type(e).__name__}: {str(e)[:80]}")
                time.sleep(3.0)
                n1 = len(reqs)
                print(f"    [{label}][{i}] ok={ok} reqs {n0}→{n1} new={reqs[n0:n1]}")
                report.setdefault("pw_clicks", []).append(
                    {"label": label, "i": i, "ok": ok,
                     "reqs_before": n0, "reqs_after": n1, "new_reqs": reqs[n0:n1]})
                try:
                    page.keyboard.press("Escape")
                except Exception:
                    pass
                if n1 > n0:
                    print(f"  ✅ 命中！「{label}」[{i}] 触发了新请求")
                    break
            else:
                continue
            break

        try:
            page.screenshot(path=os.path.join(OUT_DIR, "probe5_after.png"), full_page=True)
            print(">>> 截图 probe5_after.png")
        except Exception:
            pass

        report["all_reqs"] = list(reqs)
        with open("probe_jd_more.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("\n>>> 结果写入 probe_jd_more.json")
        print(">>> 全部请求:")
        for x in reqs:
            print("   ", x)
        try:
            input(">>> 按回车关闭浏览器…")
        except Exception:
            pass
        try:
            context.close(); browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n>>> 已中断（Ctrl+C）。")
    except Exception:
        traceback.print_exc()
        try:
            input(">>> 出错了，按回车关闭…")
        except Exception:
            pass
