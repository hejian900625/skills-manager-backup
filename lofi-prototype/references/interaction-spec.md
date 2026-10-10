# 交互规范

## 1. 状态矩阵（每个可交互元素必须覆盖）

| 状态 | 视觉表达 | 实现方式 |
|---|---|---|
| Default | 白底 + `--line` 描边 + `--ink-700` 文字 | 基础类 |
| Hover | 底 `--fill-100`，描边转 `--line-strong`，文字转 `--ink-900` | `:hover`，0.12s |
| Active / Pressed | 底 `--fill-150` + 内阴影 | `:active`，瞬时 |
| Focus | 2px 墨色外环（`outline`），**不用蓝色** | `:focus-visible` |
| Selected | 底 `--fill-150` / 主操作反色；导航项左侧 2px 墨色条、标签页 2px 下划线 | `.is-selected` / `.is-active` |
| Disabled | 底 `--fill-200`，描边 `--line-soft`，字 `--ink-300`，`pointer-events:none` | `[disabled]` / `.is-disabled` |
| Loading | 文字透明 + 居中灰 spinner（主按钮为白 spinner）；区块用骨架屏或半透明遮罩 | `.is-loading` / `.is-loading-rel` |
| Error | 控件描边 `--danger` + 底 `--danger-fill` + 下方红字；仅红色 | `.field.has-error` |
| Read-only | 底 `--fill-50`，可聚焦不可编辑 | `.is-readonly` / `readonly` |
| Empty | 灰图标 + 标题 + 说明 + 主行动按钮 | `.empty` |

**状态优先级**：`disabled > loading > error > selected > hover > default`。
**反馈时延**：hover/focus ≤120ms；页面切换 ≤160ms；抽屉/侧边栏 220ms；Toast 停留 2.2s。

## 2. 页面跳转

- 路由为 hash 路由：`#/<page-id>`，支持浏览器前进/后退。
- 声明式：**任何元素加 `data-goto="<page-id>"` 即可跳转**（`a`/`button`/`div`/`tr`/流程节点均可）。
- `data-push="false"` 表示不压入返回栈（如登录后进首页）。
- `[data-back]` 触发返回；浏览器模拟栏的返回按钮在无历史时自动禁用。
- 跳转时自动：切换页面 → 更新模拟栏标题/编号/地址 → 同步侧边导航与底部标签栏高亮 → 同步流程图当前节点 → 关闭所有浮层 → 滚动置顶。
- 表格整行 `data-goto` 时，行内的 `input/label/button/a/.select` 点击**不会**误触发跳转。

## 3. 声明式交互 API（无需写业务 JS）

| 属性 | 作用 | 常用附加属性 |
|---|---|---|
| `data-goto="id"` | 页面跳转 | `data-push="false"` |
| `data-back` | 返回上一页 | |
| `data-modal-open="#id"` | 打开弹窗 | |
| `data-drawer-open="#id"` | 打开抽屉 | |
| `data-sidebar-open="#id"` | 打开移动侧边抽屉 | |
| `data-close` | 关闭所在浮层（遮罩/抽屉/侧边栏/遮罩层） | |
| `data-tab="key"` | 标签页切换（配合 `[data-tab-group]` 与 `[data-tab-pane="key"]`） | |
| `data-collapse="#id"` | 折叠/展开（自动维护 `aria-expanded`） | |
| `data-loading="1200"` | 按钮进入 loading，`1200` 为毫秒 | `data-loading-done="文案"`、`data-loading-goto="pageId"` |
| `data-skeleton="#id"` | 目标区块显示加载遮罩 | `data-skeleton-ms="1400"` |
| `data-toast="文案"` | 弹出 Toast | `data-toast-type="error"` |
| `data-check-all` | 全选/反选（容器内复选框） | 配合 `[data-check-scope]` |
| `data-selectable` | 表格行可选中（单选高亮） | |
| `th.sortable` | 表头排序（视觉切换 ↑/↓） | |
| `data-icon="name"` | 自动注入线性 SVG 图标 | `data-icon-size="14"` |

可用图标名：`menu search close chevronDown chevronRight chevronLeft arrowRight arrowLeft plus minus check trash edit user home bell filter more eye upload download calendar image warn info star clock setting logout inbox list grid refresh`

## 4. 表单校验

- 在 `<form>` 上声明 `data-validate`，控件上声明 `data-required`。
- **字段容器**：引擎优先取控件所在的 `.field`；若找不到，则回退到控件所在的 `label.check`
  （即复选框 / 单选可直接写 `<label class="check"><input data-required …>`，不必强行包一层 `.field`），
  并在该 label 之后自动补一个 `.field-error` 承载红色文案。**两种写法都不要手写 `field-error` 占位。**
- **`label.check` 包在 `.field` 里时例外**：此时容器是 `.field`，`errElOf` 走 `field.querySelector('.field-error')` 分支，
  **不会自动补元素**。因此「`.field` + 复选框组」的写法必须手写一个空的 `<span class="field-error"></span>`
  （放在 `.check` / `.check-stack` 之后），否则只会出现红框、没有红字提示。
- **单选组（radio group）不支持整组必填校验**：引擎按**单个 radio** 校验 `ctrl.checked`。
  若只给组内第一个 radio 加 `data-required` 并默认选中，用户改选其它项会被误判为「未填」。
  因此**不要把 `data-required` 写在 radio 上**；需要用单选承载必填时，改为「默认选中一项 + 其余字段必填」，
  或直接换用下拉 / 复选框。
- 内置规则 `data-rule`：`phone`、`email`、`min:n`、`max:n`，提示文案用 `data-rule-msg` 覆盖。
- 提交时：逐项校验 → 错误字段加 `.has-error`（红描边 + 红字）→ Toast 汇总错误数 → 自动滚动并聚焦首个错误项。
- 用户重新输入即清除该字段错误态。
- 提交按钮可同时声明 `data-loading="900"`，校验通过后才进入 loading，再执行成功动作。
  **提交按钮必须写在 `<form>` 内部**：若用 `form="xxx"` 把按钮放到表单外（例如顶栏），
  点击处理器会命中 `[data-loading]` 分支并 `preventDefault()`，表单不会被提交——表现为「按钮转圈但什么都没发生」。
- 成功动作：`data-success="文案"`（Toast）、`data-success-goto="pageId"`（跳转）、`data-success-close="#modal"`（关闭弹窗）。

## 5. 浮层规则

- 打开方式：`data-modal-open` / `data-drawer-open` / `data-sidebar-open`。
- 关闭方式：关闭按钮 `[data-close]`、点击遮罩、按 `ESC`、页面跳转时自动全部关闭。
- 打开时锁滚动并聚焦首个可聚焦元素；关闭后恢复。
- 移动端（≤767px）弹窗自动贴底变底部抽屉，底部按钮平分宽度。
- 危险操作必须二次确认：标题与确认按钮用红色，文案说明「不可恢复」及影响范围。

## 6. 交互设计依据（评审口径）

1. **可预测**：同类操作位置与样式一致，主操作每屏唯一且位于视觉终点（右上/底部）。
2. **即时反馈**：任何点击在 120ms 内必须有视觉响应（变色、loading、Toast 三选一）。
3. **可撤销优于可确认**：删除类必须二次确认；非破坏性操作仅 Toast 提示。
4. **状态可见**：加载、空、错误、禁用、无权限五种异常态必须显式设计，不能留白。
5. **容错**：校验前置（输入时）+ 提交时双保险；错误定位到字段级。
6. **减少决策成本**：危险操作视觉上唯一使用红色，形成稳定语义映射。
7. **一致性**：所有间距/尺寸/圆角取自 4pt 栅格与三档控件高度，保证高保真阶段可 1:1 还原。
