# PM线稿原型 · lofi-prototype

低保真原型绘制 Skill

零依赖单文件产出：生成的原型是一个 .html 文件，双击即可在浏览器打开，可直接点击走通页面跳转与交互。

## 安装（3 步）

1. 解压得到 `lofi-prototype/` 文件夹
2. 放到本机 skills 目录：
   - macOS / Linux：`~/.workbuddy/skills/`
   - Windows：`%USERPROFILE%\.workbuddy\skills\`
3. 重启客户端（或新建会话）即生效

> 如果你只想看效果、不安装：直接双击 `assets/example.html`。

## 怎么用

对话里直接说需求即可，例如：

```
画一个 XX 产品的原型
用 lofi-prototype 把这份 PRD 转成线框图
给 XX 功能加一版低保真原型，要覆盖空状态和校验错误
```

进阶：用脚手架先建骨架，再往里填页面

```bash
python3 ~/.workbuddy/skills/lofi-prototype/scripts/scaffold.py ./my-proto \
  --name "项目名称" --pages "P1:登录,P2:列表,P3:详情"
# 加 --example 可直接生成一份完整参考示例
```

## 目录说明

| 文件 | 作用 |
|---|---|
| `SKILL.md` | Skill 主入口，触发条件、执行流程、交付说明模板 |
| `assets/icon.png` | 512×512 平台展示图标（白底） |
| `assets/icon-transparent.png` | 512×512 透明底版 |
| `assets/icon.svg` | 图标矢量源文件，可任意缩放 |
| `assets/lofi.css` | 设计系统：design token + 40+ 组件 + 六类交互状态 + 响应式 |
| `assets/lofi.js` | 交互引擎：hash 路由、弹窗/抽屉/下拉/校验/加载态，业务页零 JS |
| `assets/shell.html` | 最小页面骨架 |
| `assets/example.html` | 完整参考实现（10 页，含全部组件与状态） |
| `references/design-tokens.md` | 配色 / 字号 / 圆角 / 间距 / 栅格 |
| `references/component-spec.md` | 逐组件的尺寸、描边、状态样式 |
| `references/interaction-spec.md` | 交互 API（`data-*` 一览）与状态矩阵 |
| `references/output-checklist.md` | 交付自检清单（六组） |
| `scripts/scaffold.py` | 一键初始化原型项目 |

## 设计约束（改原型时请遵守）

- **配色**：仅灰阶 + 白；红色 `#d93025` 只用于必填、校验错误、危险操作、错误提示、异常标签、待确认批注六类场景
- **控件高度**：只取 28 / 32 / 40（移动端触控升到 40）
- **圆角**：2（按钮·输入框·标签）/ 3（卡片）/ 4（弹窗）/ 全圆（头像·步骤圆点）
- **间距**：走 4pt 栅格变量，不写裸值
- **图标**：用 `data-icon="名称"` 注入线性 SVG，不要用 emoji
- **响应式**：切到手机档时组件真实重排（侧边导航→抽屉、表格→卡片列表、弹窗→底部抽屉）

## 依赖

无。纯 HTML + CSS + 原生 JS，离线可用。
