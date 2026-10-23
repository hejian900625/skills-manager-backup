# ADAPTATION — anatomy（WorkBuddy 适配说明）

本文件由本地安装流程生成，**不属于上游仓库**。上游 `SKILL.md` / `README.md` / 代码一行未改，升级时直接覆盖即可。

## 1. 来源

| 项 | 值 |
|---|---|
| 来源路径 | `D:\source_code\anatomy`（本地 git 克隆） |
| 上游仓库 | https://github.com/wheresryan22/anatomy |
| 分支 / 提交 | `e948829`（Merge pull request #81），`main` |
| 许可 | MIT |
| 落点 | `C:\Users\Lenovo\.workbuddy\skills\anatomy`（用户级，全项目可用） |
| 包体 | 12 MB（`examples/` 11 MB 占大头，`kit/` 724 KB，`scripts/` 377 KB，`references/` 316 KB） |
| 已剔除 | `.git/`、`.github/` |

包内文件：`SKILL.md`、`README.md`、`CHANGELOG.md`、`agents/openai.yaml`、`evals/evals.json`、`kit/`（iso-kit、lathe、tube、audit、gl、turn + `kit/react/`）、`references/`（9 篇 craft/motion/verify/webgl/3d/react/kit/publish/walkthrough）、`scripts/`（capture、drive、lines、publish、turn-check、inline-kit 等）、`tests/`、`examples/`（8 个完整示例）。

## 2. 安全审计

**定级：P1（含可执行 Node 脚本 + 一个显式发布脚本），无 P0。**

| 判据 | 结论 |
|---|---|
| 可执行代码 | 有，但全是本地 Node ESM 脚本（几何生成、无头 Chrome 截图、几何审计）。无 shell 管道、无 `curl\|bash` |
| 依赖 | **零依赖**：无 `package.json`，全部 `import` 都是相对路径，不触发 npm/pip 安装 |
| 数据外发 | 仅 `http://127.0.0.1:<port>` 的 Chrome DevTools 协议（本机回环），无远程上报、无 webhook、无 base64 管道 |
| 提示注入 | 未检出（无「忽略先前指令」/「覆盖系统提示」/「不要告诉用户」类文本） |
| 凭据读取 | 不读 SSH key / token / `.env` / cookie。只读 `CHROME_PATH`、`LOCALAPPDATA`、`NODE_PATH`、`ANATOMY_PROOF_DIR` 四个环境变量 |
| 破坏性动作 | `rmSync(recursive)` 仅作用于自己创建的临时 Chrome profile 目录和 publish 的 staging 目录 |
| 上游自述一致性 | README 与仓库一致（8 个示例目录、`kit/`、`scripts/` 全部存在） |

**唯一需要人工把关的点**：`scripts/publish.mjs` 会把成品图推到 Anatomy 社区画廊（`git fetch` / `git push --force` 到自己新建分支，`gh` 提交 PR）。它要求用户自己提供一个 `anatomy-community` 克隆目录，且**只有用户明确说「发布到画廊」时才会跑**。日常做图不会触发。不主动执行。

## 3. 路径映射（上游假定 → WorkBuddy 实际）

| 上游写法 | WorkBuddy 落点 / 替代 |
|---|---|
| 技能根目录相对路径（`kit/`、`examples/`、`scripts/`、`references/`） | 以 `C:\Users\Lenovo\.workbuddy\skills\anatomy\` 为根解析；脚本里用绝对路径或先 `cd` 到该目录 |
| `npx skills add … -g -a claude-code` → `~/.claude/skills/anatomy` | **不使用**。WorkBuddy 不读 `~/.claude/skills`，已直接落盘到 `~/.workbuddy/skills` |
| `/anatomy`、`$anatomy` 斜杠命令 | WorkBuddy 无斜杠命令入口，靠 SKILL.md 的 `description` 自动匹配触发，或显式引用 `anatomy` 技能 |
| `node build.mjs`（要求 Node ≥ 20.10） | 用托管 Node：`C:/Users/Lenovo/.workbuddy/binaries/node/versions/22.22.2-6/node.exe`（v22.22.2） |
| Chrome / Chromium（截图与校验） | 本机已有 `%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe`，`scripts/capture.mjs` 的候选列表覆盖该路径；另有 Playwright chromium 可作 `CHROME_PATH` 兜底 |
| 成品图建议放 `examples/` 旁边对比 | 改为放到当前工作区目录（如 `D:/WorkBuddy/<session>/figures/`），不要污染技能包 |

## 4. 与已装技能的分工

- **anatomy**：技术概念的「等距机械图」——把抽象机制映射成真实机器，输出 SVG/WebGL 交互图。只在需要*解释性插图*时用，不做 UI 界面。
- **archify** / **answer-me-with-html** / **lofi-prototype**：偏界面、版式、原型与回答载体；anatomy 出的是装置图，不是页面骨架。三者不重叠。
- **screenshot-to-code**、**playwright-cli**：截图与浏览器自动化；anatomy 的 `scripts/capture.mjs` 只服务自己的图，不外派。

## 5. 安装验证（已实跑）

| 检查 | 结果 |
|---|---|
| Node 版本 | `v22.22.2` ✅ |
| 示例构建 `node examples/dial-indicator/build.mjs` | `wrote dial-indicator.html` ✅（136 KB 单页） |
| 无头 Chrome 截图 `node scripts/capture.mjs <page> --out …` | `saved …png`、`clip 395,64 650x485`、`readout "block 1 · reads 18.0 px"`、`console: clean`、`scrolls sideways: no` ✅ |
