# ADAPTATION.md — archify (第三方社区 skill 安装记录)

## 1. 来源
- 仓库：https://github.com/tt-a1i/archify （MIT，public）
- 作者：tt-a1i
- 分支：main（归档 tar.gz/refs/heads/main 拉取，gzip 头 `1f8b0800` 校验通过，非 404 HTML）
- 版本：SKILL.md metadata `version: "3.0"`；`archify/package.json` `version: "3.0.1"`
- 上游溯源：`based_on: Cocoon-AI/architecture-diagram-generator (MIT, v1.0)`
- 归档大小：32MB（含 website/viewer/docs/examples 等仓库噪音）；实际 skill 包 `archify/` 子目录 344 文件，已剥离前缀安装
- 安装时间：2026-10-08
- 包体文件清单（skill 包内）：SKILL.md、bin/（archify.mjs 等 7 个 CLI）、scripts/（*.mjs 构建校验脚本）、references/（8 个 md）、renderers/、schemas/（6 个 json+md）、examples/（json 样例）、brand-marks/、THIRD_PARTY_NOTICES.md、package.json
- ⚠️ 注：该仓库 star 数异常（2026-10-08 单日约 79,432★），增速不寻常；已做内容审计确认无恶意，但真实性建议后续自行核实作者/提交历史。

## 2. 审计结论：P2（安全，可直接装）
逐条判据：
- 可执行代码：`bin/archify.mjs` 等 CLI + `scripts/*.mjs`。`bin/archify.mjs` 仅用 `fs.readFileSync` 读**用户指定的输入/输出文件**，无 `child_process` 执行外部命令（除 `spawn(process.execPath,...)` 调自身子进程跑 finalize 各阶段）。
- 数据外发：**无 POST / 无 WebSocket / 无 XMLHttpRequest / 无 base64 上传 / 无读 .env**。唯一网络行为在 `scripts/check-update.mjs`：向 `https://tt-a1i.github.io/archify/skill-updates/archify/stable.json` 发**只读 GET** 取版本清单（line 1394 `fetchImpl(manifestUrl)`）。可被 `ARCHIFY_UPDATE_CHECK_DISABLED=1` 关闭；SKILL.md 明确"never install or update on your own initiative"。
- 提示注入：**无** "忽略先前指令 / 覆盖系统提示 / 不要告诉用户" 等字样。SKILL.md 为正常架构图生成指令。
- 凭据读取：**无** SSH key / token / browser cookie / `/etc/passwd` 读取。`process.env` 仅透传给子进程，不读取机密；仅读 `LOCALAPPDATA`/`XDG_CACHE_HOME` 作为更新缓存目录。
- 破坏动作：**无** `rm -rf` / `git push --force` / 无确认删除。agent 运行 `node bin/archify.mjs finalize ...` 仅在当前工作区建 `.archify/<type>-<slug>-<时间戳>/` 目录写图表，不破坏既有文件（每次新请求新目录）。
- 依赖下载：`archify/package.json` 为 `private:true`，**无 postinstall 自跑钩子**。devDependencies（ajv/parse5/saxes/simple-icons/skills/yaml）仅 `scripts/` 校验用；`bin/archify.mjs` 为单文件、大概率仅依赖 node 内置模块。
- 自述一致性：SKILL.md 与包内 `bin/schemas/examples/references` 实际存在，一致（非目录站虚标）。

**唯一低风险点**：可选的联网更新检查（只读、作者自有域名、可 env 禁用、SKILL 已禁止自更新）。不阻断安装。

## 3. 路径映射表（上游假定 → WorkBuddy 实际）
- 上游假定 `bin/archify.mjs` 在 PATH/包内 → 实际：`C:/Users/Lenovo/.workbuddy/skills/archify/bin/archify.mjs`
- 上游工作区 `.archify/<folder>/` 输出 → 同义，落在 agent 当前 cwd
- 用户级身份文件（SOUL/USER/MEMORY）→ `C:/Users/Lenovo/.workbuddy/`，本 skill 不触碰
- 上游提到的 Claude Code/Codex 适配 → WorkBuddy 已装在 `~/.workbuddy/skills/archify/`，由 Skill 工具调用

## 4. 与已装 skill 分工
- 纯架构图/流程/时序/数据流/状态机可视化 → 本 skill。
- 与 `proactive-agent`、`ixhlink-skills-self-improving` 无功能重叠，不双写。
- 注意：本 skill 的 `finalize` 含 `browser-check` 真实浏览器校验门，运行需 Node≥18 + 可用无头浏览器（环境 managed python 已含 playwright/chromium；node 侧若缺浏览器该门可能失败，属运行时问题非安全）。

## 5. 运行方式（WorkBuddy 内）
```
node "C:/Users/Lenovo/.workbuddy/skills/archify/bin/archify.mjs" doctor
node "C:/Users/Lenovo/.workbuddy/skills/archify/bin/archify.mjs" finalize <type> <candidate.json> <output.html> --quality showcase --json
```
更新检查可关：`ARCHIFY_UPDATE_CHECK_DISABLED=1 node ...`
