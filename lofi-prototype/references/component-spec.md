# 组件规范清单

类名即契约。**同一语义必须复用同一 class，禁止内联写死样式**。完整实现见 `assets/lofi.css`，活文档见 `assets/example.html` 的 P9 页。

## 布局

| 组件 | 类名 | 规范 |
|---|---|---|
| 舞台切换条 | `.stage-bar` + `.seg button[data-w]` | 顶部固定，切换 1440/768/375/自适应 |
| 视口容器 | `.stage` > `.app` | `.app` 是容器查询上下文，页面必须包在内部 |
| 页面 | `.page[data-pid][data-title]` | 每页唯一 id；路由靠 id 跳转 |
| 浏览器模拟栏 | `.browser-bar` | 返回按钮 + 页面编号 + 地址，原型感与导航 |
| 骨架 | `.shell > .sidebar + .scrim + .main > .topbar + .content` | `.scrim` 仅移动端抽屉遮罩 |
| 栅格 | `.grid` + `.col-3/4/5/6/7/8/9/12`、`.auto-2/3/4` | 12 栏；移动自动单列 |
| 弹性 | `.stack(-sm/-lg)` `.row(-md/-lg/-top)` `.spacer` `.grow` | 间距走变量 |
| 卡片 | `.card > .card-hd / .card-bd / .card-ft` | 描边 `--line`，圆角 3，内边距 16 |
| 面板 / 浅底块 | `.panel` / `.well` | 分隔线 `--line-soft` |
| 统计块 | `.stat > .stat-label/.stat-value/.stat-delta` | 数值 24px，tabular-nums |
| 移动底部导航 | `.tabbar > .tb` | 高 56，仅 ≤767px 显示 |

## 按钮 `.btn`

| 变体 | 类名 | 说明 |
|---|---|---|
| 主操作 | `.btn-primary` | 深灰实底 + 白字，每屏**最多 1 个** |
| 次级 | `.btn-secondary` | 白底 + 深灰描边 |
| 默认 | `.btn` | 白底 + 常规灰描边 |
| 文字 | `.btn-ghost` | 无边框无底色 |
| 危险 | `.btn-danger` / `.btn-danger-solid` | 红色描边 / 红色实底，仅不可逆操作 |
| 尺寸 | `.btn-sm(28)` / 默认(32) / `.btn-lg(40)` | |
| 块级 | `.btn-block` | 移动端弹窗脚、表单主按钮 |
| 图标 | `.btn-icon` | 正方形，边长同高度档 |
| 按钮组 | `.btn-group` | 相邻边框合并，选中项反色 |

状态：`:hover` 底 `--fill-100` + 描边转深；`:active` 底 `--fill-150` + 内阴影；`:focus-visible` 2px 墨色外环；`[disabled]/ .is-disabled` 底 `--fill-200` + 字 `--ink-300` + `pointer-events:none`；`.is-loading` 文字透明 + 居中灰 spinner（继承主按钮白 spinner）。

## 表单

| 组件 | 结构 | 规范 |
|---|---|---|
| 字段 | `.field > .field-label(+.req) + 控件 + .field-hint / .field-error` | 垂直间距 6；`.field-inline` 横排（移动自动竖排） |
| 输入框 | `.input` / `.textarea` / `.input-sm` / `.input-lg` | 高 32，圆角 2，内边距 0 10；focus：描边转墨色 + 2px 外环 |
| 前后缀 | `.input-affix > .affix + .input` | 图标 14，占位符 `--ink-400` |
| 输入组 | `.input-group` | 多控件拼接，中间边框合并 |
| 下拉 | `.select > button.select-trigger > .sel-val + .caret`，`.select-menu > .opt` | JS 接管展开/回填/回收；`.opt.is-selected` 反灰；`.opt.is-disabled` 不可选 |
| 复选框 | `label.check > input + span.box + 文字` | 方框 15×15 圆角 2；勾选后实底 + 白色对勾；`indeterminate` 为横线 |
| 单选 | `label.check.radio` | 圆形，勾选后实心圆点 |
| 开关 | `label.switch > input + span.track` | 36×20，开启实底 + 滑块右移 16 |
| 上传 | `.upload` | 虚线描边，hover 描边转墨色 |
| 错误态 | `.field.has-error` | 控件描边红 + 底 `--danger-fill`，标签红，`.field-error` 红字显示 |
| 复选/单选错误态 | `.check.has-error` | 方框转红描边 + 红底；红字由引擎自动补的 `.field-error` 兄弟元素显示（无需手写） |

## 数据展示

| 组件 | 类名 | 规范 |
|---|---|---|
| 表格 | `.table-wrap > table.table(.table-mobile)` | 表头高 40 底 `--fill-50`；行高 48；`tbody tr:hover` 底 `--fill-100`；`.is-selected` 底 `--fill-150`；`.is-disabled` 灰化 |
| 排序 | `th.sortable > .sort` | 点击切换 ↑/↓，仅视觉 |
| 移动表格 | `.table-mobile` + `td[data-label]` | ≤767px 自动转卡片列表，`data-label` 变行内标签 |
| 列表 | `.list > .list-item` | 高自适应，内边距 12 16，hover 底 `--fill-100` |
| 分页 | `.pagination > .pg` | 32×32，当前页反色，禁用灰 |
| 标签 | `.tag` / `.tag-strong` / `.tag-solid` / `.tag-danger` | 高 20，圆角 2 |
| 徽章 | `.badge-dot` / `.badge-dot-danger` | 18 高全圆 |
| 头像 | `.avatar` / `.avatar-sm` / `.avatar-lg` | 32/24/40，全圆 |
| 进度条 | `.progress > .bar`，`.progress-danger` | 高 6，全圆 |
| 空状态 | `.empty > .e-ico + .e-title + .e-desc` | 图标 40 灰色，说明 ≤320px 宽 |
| 骨架屏 | `.skeleton .sk-line .sk-avatar` | shimmer 微光动画 |

## 导航

| 组件 | 类名 | 规范 |
|---|---|---|
| 侧边导航 | `.nav > .nav-item` / `.nav-sub` | 项高 40，激活：底 `--fill-150` + 左侧 2px 墨色条 + 字重 600 |
| 分组标题 | `.nav-label` | 11px 大写弱化 |
| 标签页 | `.tabs > .tab` + `[data-tab-pane]` | 高 40，激活为 2px 墨色下划线；`.tabs-pill` 胶囊变体 |
| 面包屑 | `.breadcrumb` | 13px，`/` 分隔，当前项加粗 |
| 步骤条 | `.steps > .step(.is-done/.is-active)` | 圆点 24；已完成打勾，进行中反色 |
| 移动标签栏 | `.tabbar > .tb` | 图标 + 11px 文字 |

## 反馈

| 组件 | 类名 | 规范 |
|---|---|---|
| 遮罩 | `.mask.is-open` | `rgba(17,17,17,.45)`，弹窗居中（移动端贴底变抽屉） |
| 弹窗 | `.modal(.modal-sm 400/.modal-lg 840) > .modal-hd/.modal-bd/.modal-ft` | 默认 560 宽，圆角 4，底部按钮区浅底 |
| 抽屉 | `.drawer.is-open` | 右侧滑入 420 宽，移动 92vw |
| Toast | `.toast` / `.toast.is-error` | 顶部居中，2.2s 自动消失；error 用红描边红字 |
| Alert | `.alert` / `.alert-error` | 内嵌提示，error 红底红字 |
| Tooltip | `.tip > .tip-box` | 纯 CSS hover 显示，深灰底白字 |
| 区块加载 | `.is-loading-rel > .loading-mask > .spinner` | 半透明白遮罩 + 灰色 spinner |

## 原型专用

| 组件 | 类名 | 用途 |
|---|---|---|
| 图片占位 | `.ph-img`（内含 `<span>` 文案） | 斜交叉线灰块 |
| 文字占位 | `.ph-line` | 灰条 |
| 普通批注 | `.anno` | 灰底左侧 3px 深灰条，写交互/规则说明 |
| 待确认批注 | `.anno-red` | 红底，写开放问题与风险，**评审必读** |
| 热区标注 | `.hotspot` | 红色虚线框标出可点区域 |
| 流程节点 | `.flow > .flow-col > .flow-node` + `.flow-arrow > .fa-tip` | 页面跳转关系图，节点可点击跳转 |
| 图例 | `.legend > .lg > .sw` | 说明配色与状态含义 |

## 业务扩展组件（`lofi.css` 末尾，按需复用；新增时同步登记于此）

| 组件 | 类名 | 规范 |
|---|---|---|
| 内容窄栏 | `.content-inner` | 最大宽 760，居中；表单类页面避免宽屏行长过长 |
| 快捷入口磁贴 | `.card.tile` | 由 `.card` + `.tile` 组合；内边距 16，纵向 4px 间距，左对齐；图标 `.tile-ico` 灰，hover 转墨色 |
| 分类色签 | `.cat-chip` | 高 24，最小宽 44，圆角 2，`--fill-100` 底 + `--line-soft` 描边；列表行左侧标识分类，**不使用彩色区分分类** |
| 分类九宫格 | `.cat-grid > label.check.radio.cat` | 桌面 4 列 / 移动 3 列，槽距 8×12；控件高取默认档；选中态由 `:has(input:checked)` 反灰 + 墨色描边；`.is-disabled` 灰化 |
| 大号金额输入 | `.input.amount` | 高 48（移动 44），字号 24，字重 600，tabular-nums |
| 方形图标容器 | `.sq-ico` | 32×32，圆角 2，`--fill-50` 底 + `--line-soft` 描边；用于账户 / 分类行首 |
| 抽屉内表单 | `.drawer > form` | 抽屉内包 `<form>` 时必须补 `display:flex;flex-direction:column;flex:1;min-height:0`，否则 `.modal-bd` 无法滚动 |
| 实时通道状态点 | `.live-dot`（降级加 `.is-degraded`） | 6px 圆点，间距由外层 `.tag` 的 `gap:4px` 提供；已连接为实心墨点 + 1.8s 呼吸，降级为空心环且停止动画；`prefers-reduced-motion` 下关闭动画。用于表达长连接 / 推送通道的在线与降级态，**不使用彩色** |

