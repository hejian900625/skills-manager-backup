---
name: token-watcher-add-source
description: 给 token-watcher（本地多源 AI token 用量看板）新增一个数据源时的标准流程。当用户说"接入 XX 的 token 数据""给 token-watcher 加源""支持 XX 助手"时使用。覆盖：可行性判定、collector 实现、SOURCES 注册、scanner 接线、前端配色、测试夹具与全局断言对齐。
agent_created: true
---

# 给 token-watcher 新增数据源

token-watcher 的设计是「每个数据源 = 一个 collector + 注册表条目 + 一个颜色」。加源 = 6 步，必须全做，否则会出现"面板里一条无色无名堆叠段"或"健康表漏登"这类漏登记故障。

## 0. 可行性判定（CONTRIBUTING 第 0 步，硬门槛）
先确认目标工具是否把**逐请求 token 明细**以可解析形式落盘（SQLite / jsonl / zst）。没有可解析数据就别接（会永远报 0）。
- 用 `DatabaseSync(path, {readOnly:true})` 只读打开，先 `SELECT name FROM sqlite_master WHERE type='table'`，再 `PRAGMA table_info(<t>)` 看列；用真实行核验口径（抽样看 total 公式、主键性质、是否需要回看窗口）。
- 选 SQLite 类源时，抄 `src/collectors/zcode.js`（rowid/id 水位）或 `src/collectors/opencode.js`（双表水位 + 乱序回看窗口 `UPDATED_LOOKBACK_MS`）。opencode 的 `rewindIfShrunk` 和 `time_updated` 水位是处理"会删行/先插后改"表的范本。

## 1. 写 collector（`src/collectors/<tool>.js`）
- 签名：`export async function collectXxxDb(store, { path, state, version })`，返回 `{ inserted, state }`。
- 增量键：自增主键（id/rowid）水位 `Math.max(st.maxX, r.x)` + `dedup_key` 兜底幂等（INSERT OR IGNORE）。state 里存 `_v: version` 供版本落后全量重扫。
- **口径（最易错）**：先抽真实行确认 `total` 公式。通用归一模型：
  - `input_tokens` 入库时**扣掉 cache_read**（OpenAI 风格 input 含缓存命中），`cached_input = cache_read`，`cache_write` 独立成列，`reasoning_tokens` 独立成列、**不进 total**。
  - `total_tokens` 优先**直接采用上游表内值**（保证对账一致，不重算），除非上游 total 不可信。
  - 每个事件字段：`ts, tool, model(normalizeModel), session_id, project, input_tokens, cached_input, cache_write, output_tokens, reasoning_tokens, total_tokens, dedup_key`。`store.insertEvent` 处理 0 输出补齐（见 store.js 的 `_supersedeEvent`）。
- `model` 走 `normalizeModel`（src/models.js，小写 + 别名表）。看不懂的别名（如 Marvis 的 `main-auto` 智能体角色）先原样保留，**不编造**价。
- 只读不写；`is_local` 与否、是否扣用户厂商 key，决定要不要标 `apiBilled`（见下）。

## 2. 注册 `src/config.js`
- `SOURCES` 数组加条目：`{ tool, label, roots, kind:'sqlite'|'jsonl'|'zst'|'poller', collector, version }`。
- **roots 用 getter 避开 import 期求值**（关键坑）：若源路径依赖 `process.env.APPDATA`，而 config.js 在测试 import 时还指向真实 APPDATA，会把真机数据算进 roots。写成
  ```js
  get roots() { return xxxDbPaths(); }
  ```
  让它在扫描期（已设好测试 APPDATA 覆盖）才求值。纯 HOME 路径的源（claude/codex）无此问题。
- 多账号/随机目录：函数里 `readdirSync(userDir).map(a=>join(userDir,a,'database','data.db')).filter(existsSync)` 动态枚举；无 db 的账号被 `existsSync` 过滤跳过。
- `apiBilled: true` 仅当该源**扣用户自己的厂商 API key**（如 ccmr/dsh 路由到 DeepSeek/Kimi）。走订阅或自家额度的源（claude-code/codex/marvis）**不要标**——标了会和余额对账虚高。拿不准宁可不标。
- config.js 顶部按需补 `import { readdirSync, existsSync } from 'node:fs'`。

## 3. 接线 `src/scanner.js`
- `import { collectXxxDb } from './collectors/xxx.js';`
- `COLLECTORS` 加 `xxx: collectXxxDb,`（自带 state 的采集器直接放；无 state 的用 `async (store,args)=>({...(await collectXxxFile(store,args)), state:{_v:args.version}})` 包一层）。
- sqlite 源的目录监听 scanner 已原生支持（`dirname(root)`），无需改其它逻辑。

## 4. 前端配色（三处必须同步）
- `web/lib/theme.js`：`TOOL_COLORS[tool]` + `TOOL_LABEL[tool]`。深色底色选与现有 14 色区分度大的；仓库注释说有 `validate_palette.js` 但实际未必存在，挑明显不同的色即可。
- `web/app.js`：`LIGHT_TOOL_COLORS[tool]`（浅色加深版，保证 11px 小字可读对比度）。
- `web/style.css`：深/浅两种 `.badge.<tool>`（浅色段在 `[data-theme="light"]` 选择器下，**别忘了前缀**，否则会全局覆盖深色规则）。

## 5. 测试 `test/run.mjs`
- 在 fixture 块（HOME 临时目录内）造 `data.db` + 多账号目录 + 零用量跳过行 + 本地/云端两态；在 `env` 对象加 `APPDATA: join(HOME,'AppData','Roaming')` 让子进程扫到临时夹具（**HOME 是 mkdtemp，APPDATA 必须显式覆盖**）。
- 断言：per-tool 数量/总量、`input 扣缓存 / reasoning 不进 total` 拆账正确。
- **增量/幂等**：直接 `import` collector 用 stub store 跑两遍（第一遍 3 事件 → 补一条 → 第二遍仅 +1 → 第三遍 0）。**用副本隔离**，别污染主库（否则全局合计断言错位）。注意把第二遍返回值存进变量再传给第三遍（曾被外层 `r1=cli(['scan'])` 的同名变量遮蔽坑过）。
- 增量测试块在 fixture 块**之外**，fixture 块的 `ISO` 已出作用域 → 块内重新定义局部 `ISO`。

## 6. 同步三处全局断言（漏改会红）
- 行 ~827 `全源合计`：`total === 36850 + ATY_GOLD + DSH_T + <YOUR_GOLD>`。
- 行 ~947 summary `all_time_tokens`：表达式同步加 `<YOUR_GOLD>`。
- `事件总数` 断言：`22 + DSH_N + <你的事件数>`。
- 健康 ok 计数：`hasDsh ? 13 : 12` → 每加一源 +1（前提该源夹具产数据、健康为 ok）。
- 还有 `[2b]` 的交叉核对：`每个注册数据源都有品牌色与标签` 会自动抓漏登记（TOOL_COLORS/TOOL_LABEL 缺一个就红）。

## 验证
- 本机 `npm test` 可能坏（managed node 的 npm 路径问题）→ 直接 `node --disable-warning=ExperimentalWarning test/run.mjs`。
- **环境已知坑**：本机 dsh 源的多帧 zstd 夹具解析失败（`parse error ... s-dsh`），18 项 dsh 断言在改动前后都红，是 node:zlib 多帧 zstd 环境问题，与新增源无关——加源时若这些全红但新增源断言全绿，属预期，不是回归。

## 收口
按仓库纪律单变量提交（`git add` 仅相关文件，勿带 package-lock.json 字段重排等无关噪声），提交信息写清数据路径、口径、apiBilled 决策。
