# orders_scraper — 适配说明

## 1. 来源

- 仓库：https://github.com/Fanisting/orders_scraper
- 分支：main（master 404，main 可用，codeload 归档 14KB，gzip magic 正常）
- 作者：Fanisting，最后活动 2023-08
- 落盘文件：choose.py / taobao.py / jd.py / pdd.py / qt5.py / parse_jingdong.py / parse_taobao.py / README.md
- 已跳过：`__pycache__`（编译缓存）、`deprecated_tkinter/`（弃用）、`数据收集*.zip`（134B 空壳 zip）

## 2. 安全审计结论：P2（可直接装）

逐条判据：

- 网络外发：**无**。所有网络行为只访问平台自身订单页（buyertrade.taobao.com / order.jd.com / mobile.yangkeduo.com），无 webhook、无 `curl|bash`、无 base64 管道、无 `.env` 上传。
- 提示注入：**无**。
- 凭据读取：**无**。不读本地 token/cookie 文件，仅操作当前浏览器会话登录态（有头模式，需用户点"确定"放行）。
- 破坏性动作：**无**。不 `rm -rf`、不 `git push --force`、不覆盖系统文件；只在脚本运行目录写 `数据结果/` 子目录。
- 依赖下载：仅 `pip install playwright PySide2 bs4 lxml pandas`（正常，无 postinstall 钩子）。

低风险点（需知晓）：

- 自动登录并访问三个电商平台的**买家订单页**，属敏感操作，但全程有头可见、需手动确认。
- `jd.py` 抓取后用 BeautifulSoup 删掉了"收货人"列（隐私保护，好行为）。
- 选择器写死（class/日历结构），平台一改版就报错 → 需按当前 DOM 改 `taobao.py`/`jd.py`/`pdd.py`。

## 3. 路径映射

| 上游假定 | WorkBuddy 实际落点 |
|---|---|
| `git clone orders-scraper`（git 协议封） | codeload 归档 → `_audit` 解包（用 python tarfile，非 tar -xzf） |
| `python -m venv env`（用户级） | 建议用托管 `C:/Users/Lenovo/.workbuddy/binaries/python/envs/` 下的 venv 装 playwright |
| `python -m playwright install`（裸装） | 托管 Playwright 已装 chromium；如需独立再装 |
| `数据结果/` 输出目录 | 脚本运行目录下的 `数据结果/`（跟随 cwd） |
| PyInstaller 打 exe（README） | WorkBuddy 不打包，直接 `python choose.py` 跑 GUI 即可 |
| 上游 `qt5.py` 里 `QDesktopWidget`/`QMessageBox` 等 PySide2 | 装 `PySide2`（注意：PySide2 只支持 Python≤3.9，本机托管 3.13 装不上 → 见坑） |

## 4. 与已装 skill 的分工

- 与 `playwright-site-change-diagnosis`（诊断脚本失败）不同：本 skill 是**订单导出工具**，不是诊断流程。
- 与 `meituan-assistant` 等电商 skill 无交集（那些是下单/查券，本 skill 是**导出自己历史订单**）。
- 不写记忆、不接 LLM，纯本地脚本。

## 5. 坑（Windows + 本机托管 Python）

### ✅ PySide2→PySide6 已适配（方案 B，已落地）

托管 Python 3.13.12 装 PySide6 6.12.0 成功，改动 2 个文件：
- `choose.py`：`from PySide2` → `from PySide6`；移除 `QDesktopWidget` import；`QDesktopWidget().screenGeometry()` → `QApplication.primaryScreen().geometry()`；`.exec_()` → `.exec()`。
- `qt5.py`：`from PySide2` → `from PySide6`；`.exec_()` → `.exec()`。
- 已装依赖（托管 3.13.12）：`PySide6`、`playwright`、`bs4`、`lxml`、`pandas`。
- 冒烟验证通过：`import choose` 整条链 OK；`DateRangeSelector` 构建 OK；`QApplication.primaryScreen()` 非空。
- **跑 GUI**：`C:/Users/Lenovo/.workbuddy/binaries/python/versions/3.13.12/python.exe C:/Users/Lenovo/.workbuddy/skills/orders_scraper/choose.py`
  （需在宿主机桌面环境，Playwright 有头模式要弹窗口）
- **Playwright 有头模式**在本 WorkBuddy 沙箱可能无法弹 GUI 窗口；若弹不出，需在宿主机桌面环境跑 `python choose.py`。
- 选择器写死（淘宝 `button.search-mod__more-button___nbIba`、京东 `.next`/`[id="order02"]`、拼多多 `._13OAwPyA`），平台改版会失效。

### 🐛 修过的上游 bug（2026-10-10）

1. **错误处理里的 `.format()` 会崩**（`taobao.py`/`jd.py`/`pdd.py`）：
   异常分支的 JS 模板串用 `"..."".format(str(e))`，而 JS 里全是 `{}`，Python 视作占位符 → 抛 `KeyError: '\n const modal = document'`，把真实错误吞掉、程序直接崩。
   **修法**：`<p>错误为：{}</p>` → `<p>错误为：__ERR__</p>`，`.format(str(e))` → `.replace("__ERR__", str(e))`。三个文件均已修。
2. **淘宝等登录无提示、直接 120s 报 TimeoutError**（`taobao.py`）：
   原来 `page.wait_for_selector('#bought')` 一次性等 120s，未登录就死等。改为**轮询 5 分钟**，超时后 dump `url/title/body 前 500 字` 到日志与 stdout，并抛带指引的 `RuntimeError`，用于区分「没登录」和「淘宝改版」。
3. **`qt5.py` 年份写死 `range(2020,2024)`** → 改为 `start_year=2003` 到当前年份（可调常量）。

### 🔄 平台改版：淘宝 + 京东（2026-10-10 真机诊断）

两个平台订单页都已改版，上游旧选择器全部失效。**诊断方法统一为：写 probe 脚本登录后 dump 真实 DOM。**

**淘宝**（`probe_taobao.py` → `probe_taobao_result.json`）
- 旧选择器全废：`#bought` / `tp-bought-root` / `.pagination-item` / `rc-calendar-*` / `search-mod__more-button___nbIba`。
- **新版自带「导出订单」按钮，点击直接下载表格** → 已写 `taobao_export.py`（等登录 → 点导出 → `expect_download` 捕获下载）。
- 用户最终**手动导出**，淘宝侧脚本暂不深追。

**京东**（`probe_jd.py` → `probe_jd_result.json`，URL `order.jd.com/center/list.action`）
- 新版是 **React SPA（Vite）**；旧 `[id="order02"]` / `.next` / `span.dealtime` 全废。
- **无导出按钮**；**无分页**（`pagination:0`）→ 滚动加载；默认「近3个月订单」。
- 真实 DOM：订单卡 `[class*="orderCard-"]`，内部 `orderTime-*` / `orderMetas-*` / `orderBody-*` / `productItem-*`；顶层 id 有 `root` / `orderLite`。class 带哈希（CSS Modules），**用前缀匹配**。
- 已写 `jd_export.py`：**v2 改为直接解析订单 API 响应**（`data.orderList`），比抓 DOM 可靠且字段更全。
  - 字段：`orderId` / `dateSubmit` / `statusInfo.orderStateName` / `itemPayInfo.shouldPay`(实付) / `totalPrice`(原价) / `paymentTypeName` / `shopInfo.shopName` / `wareList[].name,num` / `consigneeInfo` / `data.totalNum`。
  - 流程：监听响应 → 识别含 `data.orderList` 的接口 → 滚动加载累积多页 → 去重 → 写 `数据结果/jd_orders_<date>.xlsx`+`.csv`（字段已清洗，无换行）。
  - 同时把接口 URL + postData 写入 `数据结果/jd_api/_urls.txt`（用于判断能否传日期范围拉更早订单），原始响应存 `jd_api/raw_*.json`。
  - 离线用真实响应验证解析正确（3 单：¥20.26/9.9/27.29，店铺与商品均对；API 的商品比 DOM 更全）。
- 依赖新增：`openpyxl`（写 Excel）。
- **默认「近3个月订单」**：如需更早，看 `_urls.txt` 里接口是否支持日期/页码参数。

### 🔎 京东「更早订单」攻关（2026-10-10）

- v2 跑通：CSV 干净（3 单全对）。
- 接口锁定：`POST https://api.m.jd.com/api?functionId=pcorder_center_list&source=pc_order_center`，body `{"page":1,"s":4096,"d":1}`，返回含 `data.totalNum`（=3）。
  - `s:4096` = 一次拉全部（无翻页问题）；`d:1` = **时间范围**（旧版 JD 代码注释：d=1 即“近三个月”）。
  - `totalNum=3` 证明是**服务端按时间范围过滤**，不是没加载完。
- 结论（网络查证，多源互证）：京东订单页**默认只显示近3个月**，但「近3个月订单」旁有**下拉**可切「今年 / 某年 / 全部」，可翻出历史订单（订单后台长期保留）。
- 接口请求带 `h5st` 签名 → **不能伪造参数直接调**，必须走页面 UI 触发（浏览器自动签名）。
- 已写 `probe_jd_range.py`：dump「近3个月」元素祖先链 + 候选下拉控件，定位切换控件结构。
- 已给 `jd_export.py` 加**登录态持久化**（`数据结果/jd_session.json`），后续运行免重复扫码。
- **登录坑：京东扫码成功后页面停在 `passport.jd.com` 不自动跳回订单页** → 旧判据「等页面出现订单元素」永远等不到。
  **修法**：改判据为 **Cookie 含 `pt_key`** 即算登录成功，随后**显式 `page.goto(URL)`** 回订单页。已应用于 `probe_jd_range2.py` / `probe_jd_range3.py` / `jd_export.py`。

### ✅ 时间下拉破解成功（2026-10-10，三段探测）

- **京东订单页确实没有导出按钮**：之前看到的"下载"文本实为 `div.tooltipFilter-*`（"下载京东桌面版，获取订单消息更及时…"推广横幅），与导出无关。
- **时间下拉的真实结构与点击方式**：
  - 容器 `div.selectContainer-*`（box ≈ 148×36）；选项列表 `div.selectList-* > div.item-deb94d`（选中项加 `selected-*`）。
  - **用「鼠标点容器中心」(`page.mouse.click(box中心)`) 即可展开**；展开本身**不发网络请求**。
  - 选项全量：`近3个月订单 / 今年内订单 / 2025 / 2024 / 2023 / 2022 / 2021 / 2020 / 2019 / 2018 / 2017 / 2016 / 2015 / 2014 年订单 / 2014前订单`（列表可滚动）。
  - 点击某个选项时由**页面自己带 h5st 签名**发订单接口请求 → **不需要伪造参数**，只要监听响应即可拿到该范围的订单。
- 基线接口参数：`postData=body={"page":1,"s":4096,"d":1}`（`d` 随范围变化，无需自己构造）。
- **`jd_export.py` 升级到 v3**：登录 → 鼠标展开时间下拉 → **遍历每个年份选项逐个点击** → 监听 `data.orderList` 累积去重 → 写 `数据结果/jd_orders_<date>.xlsx`+`.csv`（新增 `来源范围` 列）→ 接口映射写 `jd_api/_urls.txt`。
  - 探测脚本：`probe_jd_range.py` / `probe_jd_range2.py` / `probe_jd_range3.py`（后者带截图 + 网络监听，产物 `数据结果/probe3_before.png` / `probe3_after.png`）。

### ✅ 单范围 20 条上限 + 翻页方式破解（2026-10-10，四段探测）

- **v3 首跑只拿到 148 单**，核对 `totalNum` 发现**每个时间范围接口硬上限 20 条**：
  `2022年 totalNum=81 只返回20（缺61）`、`2021年 63→20（缺43）`、`2024年 31→20（缺11）`、`2023年 26→20（缺6）`。
- **翻页方式的实测结论（`probe_jd_page.py`，目标「2022年订单」）**：

  | 尝试方式 | 是否触发第 2 页请求 |
  |---|---|
  | 鼠标移到列表中央 `mouse.wheel` 滚轮 | ❌ 无（scrollTop 已到底 4748/5454，请求数不变） |
  | JS 把所有滚动容器 `scrollTop=scrollHeight` | ❌ 无 |
  | **鼠标点击列表底部的「更多」** | ✅ **触发** `body={"page":2,"s":4096,"d":"2022"}` |

- DOM 线索：列表底部有 `div.moreWrapper-*` > `span.moreText-*`（文本「更多」）；
  **订单卡内部也有一个「更多」（点开是"删除订单"动作菜单）** → 必须**排除 `[class*="orderCard-"]` 内的「更多」**，只点列表级那个。
  列表项有 `lazyload-wrapper` / `lazyload-placeholder`（react-lazyload 骨架），但滚动**不**触发加载。
- **`jd_export.py` 升级到 v4**：每个时间范围内 `滚到底 + 鼠标点列表级「更多」`，循环直到连续 2 轮「无新请求且卡片数不增」为止；`page` 参数随之 1→2→3…。
  - 日志会打印每轮 `点击「更多」… → 新页到达：请求 a→b，卡片 c→d`，据此可判断翻页是否真的生效。
  - ⚠️ **v4 实跑失败**（CSV 仍 148 单、`_urls.txt` 11 次调用全是 `page:1`）——过滤条件「只取叶子节点 + 排除订单卡内」把真正的翻页控件滤掉了。
- **修正（用户目视确认）：翻页控件是「下一页」按钮**，不是「更多」。
  回看 `probe_jd_page.py` 的点击序列 `click_['下一页', '更多', '更多']` —— **`下一页` 是第一个被点到的**，第 2 页请求大概率来自它（此前归因给「更多」是错的）。
- **`jd_export.py` 升级到 v5**：
  - `MORE_TEXTS = ("下一页", "加载更多", "查看更多", "更多")` —— **「下一页」最高优先**。
  - `find_load_more()` 放宽为「取**最内层**同文本元素」（不再要求无子节点），仍排除 `[class*="orderCard-"]` 内的「更多」。
  - `load_all_pages()` 改为**自愈式**：每轮按优先级逐个试候选（最多 6 个），谁触发新请求就用谁；判据只看**新请求数**（翻页后 DOM 可能是替换而非追加，卡片数不可靠，但响应已被 `on_response` 全量累积）。
  - 新增 `read_time_options()` 支持下拉内部滚动读全量选项（修此前只读到 11 个、缺 `2018/2015/2014/2014前` 的问题）。
  - 新增 `_Tee`：stdout 同步写 `数据结果/jd_export.log`，事后可直接读日志排查。
- **v5 实跑（`jd_export.log` 解读）**：
  - ✅ 时间下拉**全量 15 个**已读出：`近3个月 / 今年内 / 2025 / 2024 / 2023 / 2022 / 2021 / 2020 / 2019 / 2018 / 2017 / 2016 / 2015 / 2014 / 2014前`。
  - ✅ `2018 / 2015 / 2014 / 2014前` 四个范围 **DOM 卡片数=0 且无接口请求** → 确实没有订单（不是脚本问题）。
  - ❌ 翻页仍未通：`2024/2023/2022/2021`（`totalNum>20` 的范围）能找到**恰好 1 个**候选，但 `mouse.click` 点不动（无新请求）；`totalNum<=20` 的范围**候选数=0** → 说明**翻页控件只在"还有下一页"时渲染**，那 1 个候选就是它。
  - 归因：`probe_jd_page.py` 里唯一成功的方式是 **Playwright 定位器 `locator('text="下一页"').click()`**（带可点击性检查 + 自动滚动），与裸 `page.mouse.click(x,y)` 行为不同。
- **`jd_export.py` 升级到 v6**：新增 `try_paginate()` —— 优先用 Playwright 精确定位器 `text="下一页" / "加载更多" / "查看更多"` 逐个 `click()`（失败回退 `bounding_box` + `mouse.click`），仍不行才走 JS 找列表级「更多」兜底；`load_all_pages()` 每轮调用它，判据只看新请求数。
- **v6 实跑（148 → 245 条）：`下一页` 点通了，但判断时机有 bug。**
  - ✅ `2024年 20+11=31`(=totalNum)、`2023年 20+6=26`(=totalNum) **已补全**。
  - ❌ `2022年` 只到 60/81、`2021年` 只到 60/63 —— 原因：判定"有没有新页"用的是 `click → sleep 2.4s → 数请求数`，**响应还没回来就误判为失败**，`stable` 累计到 2 就 break 了。日志铁证：
    ```
    定位到「下一页」× 1
    [API] ... 累计 117        ← 点击其实成功了
    兜底候选 1 个: 下一页@5072  ← 此时才检查，误判
    [1] 未触发新请求（已累计请求 9）
    ```
- **`jd_export.py` 升级到 v7**：
  - 新增 `_click_and_wait()`：用 **`page.expect_response(匹配订单接口, timeout=12s)`** 真正等响应，取代"睡固定秒数数请求数"。
  - `try_paginate()` 返回 `(命中文本, 是否找到控件)`；`load_all_pages()` 返回 `(卡片数, 命中文本, 翻页页数)`。
  - **控件不存在 → 立即判定到底**（≤20 条的范围秒过，不再空等）；控件存在但拉不到新页才计 stable。
  - `max_rounds` 提到 40（2022 年 81 单需 5 页）。
  - 兜底候选点击前先 `scrollIntoView` 并重算坐标（此前曾出现 `下一页@5072` 这种视口外坐标，点了等于没点）。
- **v7 实跑：暴露两处新问题（用户再次 Ctrl+C）**
  - `切换时间范围: 近3个月订单` → `下拉展开失败，跳过`。
  - `切换时间范围: 今年内订单` → `定位到「查看更多」× 1` 后长时间无动静（用户以为卡死）。
  - 根因：① `open_time_dropdown()` 每次都点容器中心，**下拉已展开时再点会把它关掉**（一开一关交替，故偶数次必失败）；② `text="查看更多"` 会在页面别处**误匹配**，点它自然拉不到订单接口，于是 `expect_response` 白等 12s × 2。
- **`jd_export.py` 重写为 v8（当前版本）**：
  - ★ **`pump(page, ms)` 取代裸 `time.sleep()`**：裸 sleep 不会驱动 Playwright 事件循环，`page.on("response")` 回调**不会被调度**（v6 误判的真正根源）。所有等待改走 `page.wait_for_timeout()`。
  - ★ **下拉：先 `dropdown_is_open()` 判断，已展开就直接读**，不再"再点一下又关掉"；并加 `current_range_text()` 识别当前选中范围。
  - ★ **翻页判据改成接口返回的 `totalNum`**：`paginate_range()` 只在「已收条数 < totalNum」时才找控件点击，取全即停 → 小范围（≤20 条）**秒过不空等**。
  - ★ **翻页控件只认 `("下一页", "加载更多")`**，删掉会误匹配的「查看更多」。
  - ★ **点击后等到新请求**：`click_pager()` 先看即时请求数，再 `wait_new_requests()` 用 `pump()` 轮询（非盲等 12s）。
  - ★ **Ctrl+C 不再丢数据**：抓取循环包 `try/except KeyboardInterrupt`，中断后照常写出表格。
  - 每个范围结束打印 `已取 N/total`，末尾打印 `各时间范围抓取情况`，缺口一目了然。
- **v8 实跑：通关，269 条（= 各范围 totalNum 之和，全取全）。**
  | 范围 | 拿到/应有 | 请求数 |
  |---|---|---|
  | 近3个月 | 3/3 | 1 |
  | 今年内 | 8/8 | 1 |
  | 2025 | 12/12 | 1 |
  | 2024 | 31/31 | 2 |
  | 2023 | 26/26 | 2 |
  | **2022** | **81/81** | 5 |
  | **2021** | **63/63** | 4 |
  | 2020 | 18/18 | 1 |
  | 2019 | 20/20 | 1 |
  | 2017 | 7/7 | 1 |
  | 2016 | 3/3 | 1 |
  | 2018 / 2015 / 2014 / 2014前 | 0（该账号这些年份无订单） | 0 |
  - 数据质量：269 行 0 空订单号 / 0 重复 / 0 换行；金额合计 ¥53,338.83；状态分布 已完成 224、已取消 38、空 7。
  - **7 条状态为空**：均为**虚拟充值/服务类订单**（`orderType=37`，店铺 `手机充值`/`流量充值`/`京东互联网医院`/`京东大药房`）。京东接口对这类订单**只返回 `statusInfo.orderState` 数值（18 / -100），不返回 `orderStateName`**，非脚本问题。
  - 年份跨度 2016-03 ~ 2026-09。

## 6. 拼多多（2026-10-10 实测取证）

**结论：拼多多没有面向买家的 PC 网页版订单中心；唯一网页入口是 H5，且只能手机号+短信验证码登录。**

实测证据：
- `https://www.pinduoduo.com/`（11303 字节）可见文本只有「拼多多 新电商开创者 / 拼多多商家入驻 / 热点资讯 / 招聘 / 帮助中心 / 举报平台 / 查快递 …」 **无个人中心、无我的订单、无登录入口** → 是招商 + 下载 App 的门户。
- `https://mobile.yangkeduo.com/orders.html`（71532 字节）title = **「我的订单」**，但**未登录 302 跳** `/login.html?from=...orders.html`，登录页文本为「打开拼多多APP / 手机登录 / 发送验证码 / 登录」→ **仅手机号+短信验证码，无扫码**。
- H5 网关接口前缀：`mobile.yangkeduo.com/proxy/api/api/...`；页面里有 `window.__SPEPKEY__`。
- 风控通道明显：`client.message.yangkeduo.com:16482/16483/api/phantom/*`、`mobile.yangkeduo.com/proxy/api/xg/pfb/a3|a4`（指纹上报）。
- `psnl_new_on_store.html` 已下线；`personal_order_result.html` 无时间参数线索。
- 订单页静态骨架里**没有**「时间/筛选/导出/近三个月」等字样（文案在 JS bundle 内，未登录无法确认；PC 端导出的说法只出现在内容农场文章里，**与官网实测不符，不可信**）。

探测脚本：
- `probe_pdd.py` —— **无头、免登录**，只验证「有没有登录墙、接口长什么样」。已跑：确认跳登录页。
- `probe_pdd_login.py` —— **有头、需你输一次手机号+验证码**；登录后取证：订单卡选择器命中数、有无「筛选/全部时间/导出」、真实请求列表，并把整页 DOM 存 `数据结果/pdd_orders_dom.html`（供离线分析，避免二次跑）。

⚠️ 风险提示：拼多多反爬是「行为审计」（`_w` 行为签名 + 触摸事件采样），自动化登录有被拦可能；且**登录态约 7 天过期**，不能像淘宝/京东那样一次扫码长期用。

### 6.1 实测登录成功后的取证结论（2026-10-10，用户已跑 `probe_pdd_login.py`）

**登录可行**（手机号 + 短信验证码一次成功，未被风控拦）；产物：`数据结果/pdd_login.json`、`pdd_orders_dom.html`、`pdd_orders.png`、`pdd_session.json`。

关键结论：
1. **登录 Cookie 判据**：`PDDAccessToken` / `pdd_user_id` / `pdd_user_uin` / `pdd_vds`（不是 `pt_key` 那种）。`pdduid` 用户号出现在所有接口 query 里（本次 = `3537433799`）。
2. **订单接口（真正的数据源）**：
   - `POST mobile.yangkeduo.com/proxy/api/api/aristotle/order_list_v4?pdduid=<uid>`
     body `{"type":"all","page":1,"scene":"order_list_h5","front_env":163,...,"anti_content":"0as..."}`
   - 另有 `POST .../api/caterham/v3/query/my_order_group?pdduid=<uid>`（首屏分组列表）
   - `anti_content` 是**行为签名**，不可伪造 → 只能「用真实浏览器滚动触发，监听响应」。
3. **页面内嵌 `window.rawData`（约 240KB）就是首屏 SSR 状态**，`rawData.ordersStore.orders` 直接给 **10 条完整订单对象**，字段远超 DOM：
   `orderSn / parentOrderSn / orderTime(Unix秒) / shippingTime / receiveTime / orderAmount(元,字符串) / displayAmount(分) / discountAmount(分) / shippingAmount / orderStatus / status / payStatus / shippingStatus / combinedOrderStatus / orderStatusPrompt(状态文案) / priceDesc.prefix("实付"/"应付"/"先用后付 实付") / trackingNumber / mall.mallName / orderGoods[].{goodsName,spec,goodsNumber,goodsPrice,thumbUrl}`。
   → **不必解析 DOM**（DOM 里 `data-test="订单状态/店铺名称/商品名称/商品图片/店铺图片"` 只够拿文字，且**不显示下单时间**）。
4. **没有时间范围筛选**：页签只有 全部/待付款/待分享/待发货/待收货/评价（`type` 0..5，`hasOrder` 全部 true）—— 与京东的年份下拉不同。
5. **没有导出按钮**（`export_found=false`）。
6. **分页是「上拉加载更多」**：`rawData.ordersStore.ordersService = {size:10, maxSize:20, maxRounds:4, offset:{"0":"MO-01-260204-521823854231223",...}}`；DOM 里有 `div.rbl-load-more`（含隐藏文案「没有更多了...」）。
7. 状态码对照（实测）：`combinedOrderStatus` 4=交易成功、5=交易已取消、7=退款成功；直接取 `orderStatusPrompt` 更省事。

### 6.2 `pdd_export.py`（导出脚本，2026-10-10 新增）

流程：复用 `pdd_session.json`（无效则走短信登录）→ 打开订单页 → 读 `window.rawData` 拿首屏 → 监听 `order_list` / `my_order_group` 响应累积去重 → **反复上拉滚动**触发加载更多（连续 3 轮无新增或出现「没有更多了」即停）→ 输出 `数据结果/pdd_orders_<date>.xlsx` / `.csv`。

字段：订单号/下单时间/订单状态/金额类型/实付金额/应付金额/优惠金额/运费/店铺/商品/件数/快递单号/订单类型/状态码/来源。

- 金额换算：`orderAmount` 已是「元」；`displayAmount`/`discountAmount`/`shippingAmount` 是**分**，需 /100。
- 下单时间：`orderTime` Unix 秒 → 本地时间；缺失时用订单号前缀（`260628-...`）还原日期。
- 已离线用 `pdd_rawdata.json` 回归：10 条全部正确（合计 ¥96.82，状态 交易成功 8 / 已取消 1 / 退款成功 1）。
- 与京东同款坑：**Playwright 里等响应必须用 `page.wait_for_timeout()`，裸 `time.sleep()` 不驱动事件循环**。

## 升级

重跑 codeload 归档 → 覆盖 SKILL.md 上游部分（上游 README 原样保留，本 SKILL.md 已含运行说明，可整份覆盖）；ADAPTATION.md 不随上游更新。
