---
name: orders-scraper
display_name: "淘宝/京东/拼多多订单抓取"
description: 自动抓取淘宝、京东、拼多多（买家侧）订单数据。基于 Playwright + PySide2 GUI，选平台 + 日期范围后自动登录并导出订单到 数据结果/ 目录。触发词：抓淘宝订单、京东订单、拼多多订单、电商订单、导出订单。
version: 0.1.0
author: Fanisting（原仓库）
license: 原仓库未显式声明，源码默认遵循其授权
---

# 淘宝/京东/拼多多订单抓取（orders_scraper）

## 触发

用户要求"抓取/导出 淘宝·天猫·京东·拼多多的订单"时调用。

## 原理

- 有头 Chromium（Playwright）打开对应平台的**买家订单页**，提示你用 App 扫码/手机验证码登录。
- 登录态保持后自动选择日期范围、翻页、导出为 `.html`（淘宝/京东）或 `.txt`（拼多多，JSON 行）。
- 输出落在脚本运行目录下的 `数据结果/` 文件夹。

## 运行方式

1. **装依赖**（在本 skill 的 venv 里）：
   ```
   python -m venv env
   pip install playwright PySide2 bs4 lxml pandas
   python -m playwright install chromium
   ```
2. **启动 GUI**：
   ```
   python choose.py
   ```
   选平台 + 日期范围 → 点确定 → 自动开浏览器登录 → 自动抓取 → 弹"结束"框 → 关闭。
3. 在 `数据结果/` 里找 `taobao_*.html` / `jingdong_*.html` / `pdd_*.txt`。
4. 可选：用 `parse_jingdong.py` / `parse_taobao.py` 把 HTML 转成 Excel（需先把文件名改成脚本里写死的名字或改脚本里的路径）。

## 平台差异

| 平台 | 登录方式 | 产出 | 风控 |
|---|---|---|---|
| 淘宝/天猫 | App 扫码 / 账密 | HTML（订单列表 div） | 中 |
| 京东 | App/微信扫码 | HTML（含翻页），自动删"收货人"列 | 较严 |
| 拼多多 | 绑定手机号验证码（不支持扫码） | TXT（order JSON 行） | 需先绑定手机号 |

## 注意

- **全程有头模式可见**，点"确定"才放行自动化；中途别动鼠标键盘。
- 拼多多需账号绑定手机号；淘宝/京东 App 扫码最稳。
- 页面改版会导致选择器失效（脚本写死了 class/日期日历），报错就按当前 DOM 改 `taobao.py`/`jd.py`/`pdd.py` 里的 selector。
- 这是**手动、低频、个人订单**工具；别拿来高并发抓商家后台或爬他人数据。

## 本机实测结论（2026-10，上游脚本已不适用，见 ADAPTATION.md）

上游 GUI 脚本按 2020 年的页面写的，三平台**都已改版**，实际使用的是本目录下的独立导出脚本：

| 平台 | 现状 | 用什么脚本 |
|---|---|---|
| 淘宝/天猫 | 「已买到的宝贝」旧选择器全废；改版后页面自带「导出订单」按钮 | 直接手动导出，或 `taobao_export.py` |
| 京东 | React SPA，无导出按钮，时间范围下拉可选到 2014 前 | `jd_export.py`（实测 269 单全量，免扫码复用登录态） |
| 拼多多 | 无 PC 网页版；H5 `mobile.yangkeduo.com/orders.html` 可用，仅手机号+短信登录 | `pdd_export.py`（实测 258 单，2017-01 起） |
| 美团 | 无 PC 订单页；统一订单中心 H5 `i.meituan.com/mttouch/page/order` 可用，手机号+短信登录 | `mt_export.py`（实测 900 单，2015-06 起） |
| 滴滴 | **网页端全线不通**（实探见下），只剩抓包路线，且 PC 微信抓不到 | 无可用脚本，见「滴滴：实探结论」 |
| 高德 | PC 网页端**无订单/无轨迹**（实探见下）；只有 `getHistory` 能拿到 60 条地点浏览历史 | `probe_amap_login.py`（取证）；暂无导出脚本 |
| 中国移动 | PC 网上营业厅 `shop.10086.cn/i/?f=billqry`，短信随机码/服务密码/App 扫码 | `cmcc_export.py`（实测 13 个月账单，2025-10 起） |

### 滴滴：实探结论（2026-10-10，成本很高，先读这段再决定要不要动手）

- **网页端无订单入口**：`www.didichuxing.com` / `www.didiglobal.com` / `web.didiglobal.com` 全是品牌/企业官网，
  官网 74 个链接里**没有一个消费者订单入口**；`h5.didichuxing.com` 303 跳占位页；
  `common.didiglobal.com` 是 SPA 网关（router/2.43.3），猜测路径 `/order`、`/orderList`、`/trip` 等**全部 404**。
- **PC 微信小程序抓包走不通**（本次已完整试过，别重复踩）：
  1. mitmproxy 装在**独立 venv** `binaries/python/envs/mitm`（不能装主环境：`service_identity` 要 cryptography≥47，
     与 f2 要求的 `==44.0.0` 冲突）；入口是 `envs/mitm/Scripts/mitmdump.exe`（**不是** `python -m mitmdump`）。
  2. mitmproxy 12 的 CA 用 `certutil -user -addstore -f Root` 装（`Import-Certificate` 要 UI 交互，会被卡住）；
     curl 测 HTTPS 要加 `--ssl-no-revoke`，否则 mitmproxy 签发的证书没 CRL 会误报失败。
  3. **系统代理必须写注册表**（`HKCU\...\Internet Settings`），用 Python `winreg` 写——
     本环境下 **PowerShell `Set-ItemProperty` / `reg.exe` 会被沙箱拦掉，且静默失败**（写完 `ProxyEnable` 仍是 0，
     让人误以为代理已开）。见 `launch_wechat_capture.py`。
  4. **决定性结论：PC 微信不走系统代理，也不读 HTTP_PROXY 环境变量**——
     开代理后启动微信（含 3 个 `WeChatAppEx.exe` 小程序进程），8899 端口 **0 条连接**，抓包日志零微信流量。
     微信 PC 用自研网络栈。要抓只能靠驱动级强制代理（Proxifier / Netsh 透明代理），本机没装。
- **建议替代路径**：① 滴滴 App 内「我的 → 钱包/发票 → 行程单」官方导出到邮箱（0 风险）；
  ② 手机端代理抓包（HttpCanary / 手机连电脑代理），滴滴 App 可能有 SSL Pinning 需实测；
  ③ 用微信/支付宝支付账单里的滴滴交易记录做金额侧近似（无行程详情）。

### 拼多多 H5 接口字段约定（踩坑记录，改代码前必读）

- 数据源两条，**字段命名和金额单位都不同**：
  - 首屏 `window.rawData` → `ordersStore.orders`，**camelCase**；
  - 上拉分页 → `POST .../order_list_v4`，响应**顶层 `orders` 数组**，**snake_case**。
- `price_desc` / `priceDesc` 在接口里是 **JSON 字符串**，在首屏里是 dict → 必须 `_as_dict()` 兼容，
  否则 `.get()` 抛 `AttributeError`，而异常又被 `except: pass` 吞掉，表现为「接口一直在请求但一条订单都没解析出来」。
- 金额单位**按值类型**判断：**字符串 → 元**（首屏 `orderAmount="16.7"`）；**数字 → 分**（需 /100）。
  首屏 `displayAmount`/`discountAmount` 也是分，不是元。
- 多多买菜订单（`type=2`、订单号 `PO-YYMMDD-…`）结构不同：商品嵌在 `orders[].order_goods`，
  没有 `order_time`（用 `group_order.create_at` 或 `sort_id` 前 10 位还原），
  没有 `order_amount`（只有 `display_amount`，且 `price_desc_v2.prefix` 明确写着「实付:」）。
- 分页无 `has_more` 字段，靠「连续 4 轮无新增」+ 页面出现「没有更多了」判定到底。
- 离线回归：`pdd_regress.py` 回放 `数据结果/pdd_api/*.json`，不联网验证解析正确性。

### 美团订单中心 H5 接口约定（踩坑记录，改代码前必读）

- **入口**：`https://i.meituan.com/mttouch/page/order`（标题「全部订单」，页签 全部/待付款/待使用/待评价/退款售后）。
  PC 端 `www.meituan.com` 是企业官网，**没有**消费者订单页。
- **首屏**：SSR 内嵌 `window.__INITIAL_STATE__`，含 `orderList`（约 20 条）与游标 `lastOrderTime`。
- **翻页**：`GET /mttouch/api/order/getOrderList?lat=0&lng=0&lastOrderTime=<游标>&status=0&shark=1&yodaReady=h5&csecplatform=4&csecversion=4.3.0`，
  游标就是上一页响应里的 `data.lastOrderTime`；**响应里没有 hasMore 字段**，只能靠「返回空 orderList」判定到底。
- **不要靠滚动翻页**（本目录曾试图照搬拼多多方案）：美团订单页是超长 H5 列表（900 条约 9 万像素），
  滚太快页面不触发加载 → 提前「假到底」（实测同一份数据两次只拿到 781 / 244 条）；
  改用**页面内 `fetch` 顺游标请求**后稳定拿到全量 900 条。
- **字段**：`orderid`/`stringOrderId`（订单号）、`showstatus`、`title`（商家）、`ordertime`（Unix 秒）、
  `orderinfo`（**展示文本数组**，如 `["1份｜…代金券","下单时间: …","实付: ￥86"]`）、`catename`（分类）、
  `partnerid`、`orderDetail`。
  → **金额没有结构化字段**，只能从 `orderinfo` 文本正则抠（「实付: ￥86」/「总价：¥33.16」）。
  → **外卖订单的 `orderinfo` 只有「下单时间/总价」，没有菜品名**（平台列表就不给），商品列会空。
- **分类补齐**：`partnerid` 缺失分类时，先用「已有分类的订单」实证出映射，再用 `KNOWN_PID` 兜底
  （137=共享单车、68=到店预订、136=排队取号、54/151=券包、51=演出票务）。
- 风控：美团有 **H5guard + dfpId 设备指纹**；接口翻页每轮间隔 1.8s，实测 46 次请求无拦截。
- 离线回归：`mt_regress.py` 回放 `数据结果/mt_api/*.json` + `mt_order_center.html`，可 0 真机重建交付文件。

### 高德：实探结论（2026-10-10）

- **登录后头像菜单实测只有「路书 / 收藏 / 退出登录 / 返回旧版」** —— 没有「我的订单」「足迹」「行程记录」。
  PC 网页版就是个地图工具站，**用户数据（打车订单、移动轨迹）只存在于 App 内**。
- 死路清单：`taxi.amap.com` → 403 OSS `The bucket you access does not belong to you`；
  `/service/taxi` → `{"status":"8","data":"404 Not found!"}`；`/myfoot`、`/footprint`、`/order` → 空壳地图页。
- 开放平台「猎鹰轨迹服务」（`lbs.amap.com/api/track`）是给开发者**上传**自己轨迹的，**读不到个人历史轨迹**；
  `es.amap.com` 是高德打车企业版（需企业资质）。
- **唯一有数据的接口**：`https://www.amap.com/service/getHistory?type=301`，登录后才返回内容（匿名 125B → 登录 34KB），
  约 **60 条 POI 搜索/浏览历史**（name / address / ts / `his_record_source`: poi_detail|search_click|tip_bar），
  只覆盖最近约 1 个月。**是"查过的地方"，不是移动轨迹。**
- **登录判据的坑（踩了两次）**：`localStorage['amap-uuid']` **匿名访问也有，且键名含 "uid"**，
  用正则 `/uid|user|token|login/i` 匹配会在首帧就误判"已登录"，整轮跑在匿名态。
  **正确判据 = 页面正文里是否还有登录框关键词（立即登录|短信登录|请输入手机号）**，正文 <50 字（未渲染完）一律判未登录。
- 网络上的"高德导出轨迹"教程多为 SEO 站编造（说法互相矛盾，还有"VIP 才能导出 HTML"），勿信。

## 中国移动：话费账单（实测可用，2026-10）

**入口**：PC 网上营业厅 `https://shop.10086.cn/i/?f=billqry`（账单查询）、
`?f=billdetailqry`（详单）、`?f=home`（我的账户）、`?f=packremainqry`（套餐余量）。
登录：`login.10086.cn`，支持**短信随机码 / 服务密码 / 中国移动 App 扫码**。
会话落盘 `数据结果/cmcc_session.json`，重跑免登录。

**关键事实**
- **接口响应全部是 AES 密文**：`/i/v1/fee/touchbillinfo/<uid>?bgnMonth=YYYYMM&endMonth=YYYYMM`
  等接口返回 `{"data":{"outParam":"<base64 密文>"}}`，前端 JS 内解密。
  → **不要试图抓接口解析，走「页面渲染后取 DOM」**。
- **月份按钮有 13 个**（2026-10 ~ 2025-10），尽管页面 meta 写"可查近 6 个月"，实际给了 13 个。
  DOM：`<a id="monthN" month="YYYYMM">2026-10</a>`，`month1` 的 id 是 `month-click`。
- **账单容器**：`#curmonth-comsum`。总额 `.zd-sum`；
  分项循环 `.zd-list-items`（大类 `.zditem-title`）→ `.zd-definite`
  （明细 `.zd-names`、原价 `.zd-ys`、减免 `.zd-jms`、实际消费 `.zd-sjs`）；
  合计在 `.zd-summation .zd-hjs.zd-ys|.zd-jms|.zd-sjs`。

**两个坑**
1. **月份列表是折叠下拉** —— Playwright `page.click("#month13")` 必超时（`element is not visible`）。
   必须用页面内 JS 触发：`page.evaluate("mid => document.getElementById(mid).click()", mid)`。
2. **详单（通话/上网/短信流水）要短信二次验证**，且含对方号码，属敏感数据 —— 未做，需用户明确要求。

**13 个月是硬上限，更早查不到（已实测证伪，2026-10）**
- 月份列表由前端硬编码生成：`for(var i=0; 13>i; i++)`；点击处理只读 `month` 属性
  （`var a=$(this).attr("month"); return S(a)`），所以改 `month` 再触发点击**能**发起任意月份查询。
- 但对 `202509`（13 个月外第一个月）发起查询后：页面内容**与 202510 完全相同**
  （同样 ¥10.00 = 套餐 8.00 + 通话 2.00），且月份标签仍显示 `2025-10`
  → **是残留渲染，不是真数据**。曾误判为"返回了数据"，已证伪。
- 连续构造更早月份（202509 → 202508）会触发风控：**登录态被踢**，session 作废，需重新登录。
- 交费记录 `?f=recharhisqry` 是**充值流水**（不是账单），页面明示"查询时间：近五个月"，
  比账单还短，不值得为它再登录一次。
- **要更早账单只能走官方渠道**：10086 转人工 / 线下营业厅打印盖章账单 / 中国移动 App 内翻页
  （各省留存期不同，通常 6 个月~2 年）。

**产出**：`cmcc_bills_*.csv/xlsx`（月度汇总 7 列）+ `cmcc_bill_items_*.csv/xlsx`（分项明细 7 列）。
实测 13 个月、30 条分项、合计 ¥162.35、0 空值。每月原始 HTML 快照在 `数据结果/cmcc_bill_raw/`。

## 上游

https://github.com/Fanisting/orders_scraper
