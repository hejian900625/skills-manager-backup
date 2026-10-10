---
name: lofi-prototype
icon: assets/icon.png
display_name: PM线稿原型
display_name_en: Lo-Fi Wireframe Prototype
description: 以资深互联网产品经理视角绘制 Axure 风格低保真线稿原型，输出可点击、可跳转、自适应桌面/平板/移动的单文件 HTML 原型，含统一组件规范、六类交互状态、页面跳转关系图与评审级交付说明。当用户要求画原型图、线框图、低保真原型、wireframe、页面流程/跳转图、交互原型、Axure 风格原型，或需要把 PRD/需求描述转成可视化原型用于评审与高保真输入时使用。
description_zh: 以资深互联网产品经理视角绘制 Axure 风格低保真线稿原型，输出可点击、可跳转、自适应桌面/平板/移动的单文件 HTML 原型，含统一组件规范、六类交互状态、页面跳转关系图与评审级交付说明。适用于要求画原型图、线框图、低保真原型、wireframe、页面流程或跳转图、交互原型、Axure 风格原型，或需要把 PRD 与需求描述转成可视化原型用于评审、对齐与高保真设计输入的场景。
description_en: Draw Axure-style low-fidelity wireframe prototypes from a senior product manager's perspective. Produces a single self-contained HTML file that is clickable, navigable, and responsive across desktop, tablet, and mobile. Includes a unified component spec, six interaction states (hover, active, focus, selected, disabled, loading, validation error), a page-flow diagram, and review-ready delivery notes covering component conventions, monochrome-plus-red color rules, and interaction rationale. Use when the user asks for a prototype, wireframe, lo-fi mockup, page flow or navigation diagram, interactive mockup, Axure-style screen, or wants to turn a PRD or feature description into a review-ready visual prototype that feeds high-fidelity design.
agent_created: true
version: 1.0.0
tags:
  - 原型
  - 线框图
  - 低保真
  - wireframe
  - prototype
  - Axure
  - 产品设计
---

# PM线稿原型（Axure Wireframe）

站在资深互联网产品经理的立场：**原型的目标是验证信息架构、任务流与交互逻辑，不是炫技。**
因此默认产出**黑白灰线稿**，只保留必要的简单交互与页面跳转；唯一的红色只服务于「警告 / 校验错误 / 破坏性操作」。

## 触发条件

出现以下任一意图即启用本 skill：

- 关键词：画原型 / 原型图 / 线框图 / 低保真 / wireframe / prototype / mockup / 页面流程图 / 页面跳转 / 交互原型 / Axure 风格 / 界面草图
- 给出 PRD、需求描述、功能列表，要求「出个原型看看」
- 要求把某个流程（登录、下单、审批、发布…）画成可点击的页面

## 参数

| 参数 | 默认 | 说明 |
|---|---|---|
| `--pages` | 由需求推导 | 页面清单，格式 `P1:登录,P2:任务列表,P3:详情` |
| `--name` | 产品原型 | 项目名称，写入标题与舞台条 |
| `--device` | 三档全给 | `desktop` / `tablet` / `mobile` / `all`；默认 `all` |
| `--flow` | `on` | 是否生成 P0 页面流程总览页 |
| `--spec` | `on` | 是否附「组件规范 + 配色规则 + 交互设计依据」交付说明 |
| `--out` | `./outputs/<项目名>-prototype/` | 输出目录 |
| `--example` | `off` | 直接以完整参考示例为起点改造 |

## 使用场景

| 场景 | 侧重点 |
|---|---|
| 需求评审 | 页面齐全 + 流程闭环 + 待确认项红标 |
| 方案沟通 / 对齐 | 跳转关系清晰，点击即可走通主流程 |
| 高保真设计输入 | 组件与状态规范已固化，可 1:1 还原 |
| 信息架构验证 | 先出 P0 流程总览，确认页面与入口 |
| 研发澄清 | 异常态（空/加载/错误/禁用/无权限）显式设计 |

## 文件索引

```
SKILL.md                     本文件：流程与约束
assets/lofi.css              设计系统（全部组件 + 状态 + 响应式）—— 直接引用，勿改
assets/lofi.js               交互引擎（路由/弹窗/校验/加载）—— 直接引用，勿改
assets/shell.html            最小骨架：复制即开工
assets/example.html          完整参考实现：6 页 + 弹窗 + 抽屉 + 全部状态
references/design-tokens.md  配色 / 间距 / 字号 / 圆角 / 栅格 / 断点
references/component-spec.md 逐组件的尺寸、圆角、边框、间距、状态规范
references/interaction-spec.md 状态矩阵、声明式 data-* API、交互设计依据
references/output-checklist.md 交付自检清单（A–F 六组）
scripts/scaffold.py          一键初始化项目目录
```

## 工作流

### S0 · 需求澄清（信息不足时，一次性收敛，最多 1 轮提问）
用 `AskUserQuestion` 在同一轮问完，不要分多次：
1. 页面范围（只画主流程 / 含异常与设置页 / 全量）
2. 平台侧重（桌面 Web / 移动 App / 平板 / 三端都要）
3. 核心任务流程（用户在该产品里要完成的 1–3 条主线任务）
4. 是否包含异常态与权限态（建议默认包含）

信息已充分则跳过，直接进入 S1。

### S1 · 抽取页面清单
从需求中提炼页面，编号 `P1…Pn`，产出表格：

| 编号 | 页面名 | 入口 | 关键元素 | 跳转去向 |
|---|---|---|---|---|
| P1 | 登录 | 启动页 | 手机号/密码/记住我 | P2 |

**P0 固定为「页面流程总览」**，其余按任务流顺序编号。

### S2 · 元素 → 组件映射
把页面元素映射到 `references/component-spec.md` 的组件表，禁止自创样式。
需要的元素若组件库未覆盖：**优先用已有组件组合**，确有必要时才扩展 CSS，并同步更新 `references/component-spec.md`。

### S3 · 生成原型
```bash
PY="C:\Users\Lenovo\.workbuddy\binaries\python\versions\3.13.12\python.exe"
"$PY" "C:\Users\Lenovo\.workbuddy\skills\lofi-prototype\scripts\scaffold.py" <输出目录> \
  --name "<项目名>" --pages "P1:登录,P2:任务列表,P3:任务详情"
```
然后逐页填充 `index.html`。结构约定：

```html
<section class="page" id="p1" data-pid="P1" data-title="页面名">   <!-- 每页唯一 id -->
  <div class="browser-bar">…返回按钮 + 编号 + 地址…</div>
  <div class="shell">
    <aside class="sidebar" id="sidebar">…导航…</aside>
    <div class="scrim" data-close></div>
    <div class="main">
      <header class="topbar">…汉堡 + 标题 + 操作…</header>
      <div class="content">…页面主体…</div>
      <nav class="tabbar">…移动端底部导航…</nav>
    </div>
  </div>
</section>
```
登录/落地页这类无导航页面，可省去 `.shell`，直接用 `.content`。

### S4 · 挂交互
全部用声明式 `data-*`，**不要写业务 JS**（完整 API 见 `references/interaction-spec.md`）。
逐页检查：主流程能点通、每个按钮有反馈、每个跳转有落点。

### S5 · 补异常态与批注
每页至少一种：空状态 / 骨架屏加载 / 校验错误 / 禁用 / 无权限。
待确认事项用 `.anno-red` 红批注；交互规则用 `.anno` 灰批注写在页面底部。

### S6 · 自检
按 `references/output-checklist.md` 六组逐项打勾；技术项执行：
```bash
cd <输出目录> && node --check lofi.js
```
并实测三档视口切换（1440 / 768 / 375）。

### S7 · 交付
`present_files` 打开 `index.html`，并按下方模板附交付说明。

### S8 · 评审返工（口径变更 / 局部返工）

评审后甲方常按红批注回话（例如"批次切换不允许审核人直接操作，必须经编排转述"）。这类改动**横跨多个页面与浮层**，按下面的顺序做，不要边想边改：

1. **先定规则，再找落点**。把口径写成一句可执行的规则（谁不能做什么、什么动作改叫什么），再列出所有受影响的位置（页面 + 浮层 + 权限矩阵 + 流程总览 + 批注）。
2. **统一动词**。改口径必然改按钮文案。为同类动作定一套动词（如"执行型"→"表态型"：`批准`→`提请裁定`、`处理`→`提请处置`），然后全文对齐，避免只改一半。
3. **定中间态**。口径从"直接执行"改为"转述执行"时，必须补一个中间态（如 `已提请 → 转述中 → 已执行`），否则用户会以为点了按钮就已生效。提交成功的文案要显式写明"不会直接改变任务状态"。
4. **一次性落盘**。改动点多于 5 处时，**不要在同一条消息里发多个并行编辑**——同一文件的并行写入会互相覆盖，只有最后一次生效（表现为"工具报成功但内容没变"）。做法是写一个一次性替换脚本：`(名称, 原串, 新串, 期望命中数)` 列表 + 单次读出、单次写回、逐项打印 `OK / SKIP(已完成) / FAIL(未找到)`。这样既无覆盖，又天然幂等可重跑。
5. **改完必复检**。重跑 S6（标签闭合 + `data-*` 引用完整性 + 残留串扫描），并同步更新 `README.md` 的"已确认口径 / 仍待确认"两节与页面底部批注。红批注里已拍板的条目要**移出待确认区**，改写为"已确认口径（本轮已落地，可对照页面核查）"。
6. **口径有歧义时给推断 + 明示**。若回话只点了部分对象（如只提了"批次切换、人工介入"，没提"回滚"），按同一原则扩展到同类动作，并在待确认区写清"这是推断，如需反向处理请拍板"——比留下一个自相矛盾的页面更好。


## 硬约束（不可违反）

1. **配色**：仅灰阶 + 白 + `#d93025`。红色只用于：必填/校验错误、危险操作、错误 Alert/Toast、异常标签、待确认批注、热区标注。其余任何色相一律禁止。
2. **自适应**：必须三档可用。响应式一律用**容器查询**（相对 `.app`），不依赖浏览器窗口宽度，保证舞台切换条生效。
3. **组件一致**：同类组件复用同一 class；间距取 4pt 栅格变量；控件高度只取 28/32/40（移动 32/40/44）；圆角只取 2/3/4/全圆。
4. **交互完整**：每个可点元素必须有行为；每个页面必须有 `data-pid` + `data-title`；每页至少一种异常态；hover/focus/selected/disabled/loading/error 六态可演示。
5. **不要写业务 JS**：交互全走 `data-*`。确需扩展时改 `assets/lofi.js` 并同步更新 `references/interaction-spec.md`。
6. **不要改 `lofi.css` 的既有 token 与组件**：新增组件在文件末尾追加，并同步更新组件规范文档。
7. **交付必带说明**：组件规范、配色规则、交互设计依据，缺一不可。
8. **输出为可直接双击打开的单目录**（`index.html` + `lofi.css` + `lofi.js`），无 CDN 依赖。

## 交付说明模板（回复中必须包含）

```markdown
## 原型交付说明

**产出**：`<路径>/index.html`（N 个页面 + M 个浮层，三档视口自适应）

### 页面清单
| 编号 | 页面 | 说明 |
|---|---|---|
| P0 | 流程总览 | 点击节点可跳转 |
| P1 | … | … |

### 一、采用的组件规范
- 控件高度：28 / 32 / 40（移动触控档 32 / 40 / 44）
- 圆角：2（按钮·输入框·标签）/ 3（卡片）/ 4（弹窗）/ 全圆（单选·开关·头像）
- 间距：4pt 基准栅格，卡片内边距 16，字段间距 16，标签与控件 6
- 栅格：12 栏，槽宽 16；桌面 4 列 / 平板 2 列 / 移动 1 列
- 组件来源：…（列出本页用到的主要组件与其类名）

### 二、配色规则
- 灰阶表达层级：`#111` 标题 → `#3d3d3d` 正文 → `#767676` 辅助 → `#bfbfbf` 禁用
- 填充表达状态：`#f4f4f4` hover → `#ededed` 选中 → `#e2e2e2` 禁用 → `#2b2b2b` 主操作
- 红色 `#d93025` 仅用于：…（列出本原型中的具体使用场景）

### 三、交互设计依据
- 跳转：…（主流程路径 + 触发条件）
- 状态：六态齐全，重点说明…
- 反馈：hover/focus ≤120ms，Toast 停留 2.2s，破坏性操作二次确认
- 依据：可预测 / 即时反馈 / 可撤销优于可确认 / 状态可见 / 容错 / 减少决策成本 / 一致性

### 四、待确认项
1. …（来自 `.anno-red` 红批注）
```

## 常见坑

- **表格整行跳转与行内按钮冲突**：行加 `data-goto`，行内 `input/label/button/a/.select` 引擎已自动排除，勿再包一层 `data-goto`。
- **表单提交按钮的 loading**：给 `type="submit"` 加 `data-loading` 时，引擎会等校验通过后再进 loading，不要手动 preventDefault。
- **`:root` 在容器查询内无效**：移动端覆盖变量要写在 `.app` 上（CSS 已处理）。
- **流程节点与页面编号要一致**：`.flow-node` 的 `data-goto` 必须等于某个 `<section class="page">` 的 id，否则点了没反应。
- **图标别用 emoji**：统一 `data-icon="名称"`，引擎注入线性 SVG。
- **必填复选框校验**：`<label class="check"><input type="checkbox" data-required>` 直接写即可，引擎会回退到 `label.check` 作为错误容器并自动补 `.field-error`；不要手写空的 `<span class="field-error">` 占位，也不要为了校验强行包一层 `.field`.
- **区块加载遮罩要定位**：`data-skeleton="#id"` 的目标元素必须是定位上下文，给它加 `style="position:relative"`，否则遮罩会溢到整页。
- **`data-tab-group` 必须包住「标签 + 面板」的共同祖先**：引擎取 `tab.closest('[data-tab-group]')`，取不到时回退到 `tab.parentElement.parentElement`。如果标签在 `.card-hd`、面板在 `.card-bd`，必须把 `data-tab-group` 写到 `.card` 上；如果标签在 `<form>` 外、面板在 `<form>` 内，写到两者的共同父级。写错的表现是「点了标签，active 变了但内容不切换」。
- **一个按钮上 `data-close` 和 `data-toast` 只能生效前者**：事件委托里 `[data-close]` 在 `[data-toast]` 之前且直接 `return`。破坏性确认要「关浮层 + 弹 Toast」，必须用 `<form data-validate data-success="已删除…" data-success-close="#modal-x">` + `type="submit"`，提交流程会先 Toast 再 close。
- **侧边导航不要每页都写 `id="sidebar"`**：`data-sidebar-open="#sidebar"` 用 `querySelector` 只会命中文档里第一个（可能在隐藏页），移动端抽屉就打不开。每页给独立 id（`#sidebar-p1`…）并让本页按钮指向自己。
- **隐藏面板里不要放 `data-required`**：`validateForm` 不区分可见性，会把隐藏 tab-pane 里的空字段一起报错，出现「明明填了却提示必填」。做法是校验按当前面板惰性执行，或只给默认展示的面板加 `data-required`。
- **`.drawer` 里包 `<form>` 要补布局**：`.drawer` 是 `display:flex;flex-direction:column`，中间插入的 `<form>` 默认 `display:block`，会让 `.modal-bd{flex:1;overflow:auto}` 失效、内容不可滚动。追加 `.drawer > form{display:flex;flex-direction:column;flex:1;min-height:0;}`。
- **多页口径返工要用单写入脚本**：同一条消息里对同一文件发多个编辑，会因并发写入互相覆盖（工具各自报成功，实际只有最后一次落盘）。超过 5 处改动时用一次性替换脚本，并对每项断言期望命中数，跑完打印 OK/SKIP/FAIL。
- **`<span>` 里套 `<div>`**：列表行内用 `<span class="row">` 保持行内语义时，里面的 `.spacer` 若写成 `<div>` 属非法嵌套（浏览器能容错解析，但校验工具会报错）。可直接改用 `<div>` 包裹整段内容。

