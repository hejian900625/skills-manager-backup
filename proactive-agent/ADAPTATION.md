# proactive-agent → WorkBuddy 适配说明

本文件由本机安装时补写，**不修改上游 SKILL.md**，便于后续直接覆盖升级。

## 来源

| 项 | 值 |
|---|---|
| 上游仓库 | https://github.com/halthelobster/proactive-agent |
| 分支 | main |
| frontmatter 版本 | 3.0.0（目录站列 3.1.0，仓库 main 实为 3.0.0） |
| 作者 | halthelobster (Hal Labs)，MIT |
| 包体 | 仅 1 个文件 `SKILL.md`（16,960 B），无 scripts / assets |

## 安装前安全审计结论：P2（可安装）

- ✅ 纯 Markdown 指令文本，**零可执行代码**：无 `scripts/`、无 shell、无 `curl|bash`、无网络请求、无凭据/环境变量读取
- ✅ 无数据外发模式（无 exfiltration、无 webhook、无 base64 管道）
- ✅ 无隐藏提示注入（无忽略先前指令、无覆盖系统提示的表述）
- ✅ 上游自述的安全立场与本机策略一致：外部内容当数据处理、外部动作需人工批准、不接 agent 社交网络
- ⚠️ 低风险点 1：会指示 agent 在工作区创建/写入多个 md 文件（ONBOARDING/SOUL/USER/AGENTS/SESSION-STATE/HEARTBEAT/TOOLS），属文件写入，非执行
- ⚠️ 低风险点 2：Quick Start 引用的 `assets/*.md` 与 `./scripts/security-audit.sh` **在上游仓库中并不存在**（悬空引用），照抄该两步会失败，见下方"路径映射"

## WorkBuddy 路径映射（照此执行，不要照抄上游的裸文件名）

上游假定工作区根目录放一堆 md。WorkBuddy 已有自己的三层记忆体系，映射如下：

| 上游概念 | WorkBuddy 实际落点 |
|---|---|
| `SOUL.md` / `USER.md` / `MEMORY.md`（用户级） | `C:\Users\Lenovo\.workbuddy\` 下已存在同名文件，直接复用，**不要在工作区重建** |
| `MEMORY.md`（项目级） | `<workspace>\.workbuddy\memory\MEMORY.md` |
| `memory/YYYY-MM-DD.md` 每日日志 | `<workspace>\.workbuddy\memory\YYYY-MM-DD.md`（append-only） |
| `SESSION-STATE.md`（WAL 目标） | 工作区根 `SESSION-STATE.md`（临时态，任务结束可蒸馏后删） |
| `memory/working-buffer.md` | `<workspace>\.workbuddy\memory\working-buffer.md` |
| `AGENTS.md` / `TOOLS.md` / `HEARTBEAT.md` | 工作区根，按需创建，非必需 |
| `ONBOARDING.md` | **跳过**（WorkBuddy 的 identity 引导已由 BOOTSTRAP.md/IDENTITY.md 承担） |
| `session_status`（判 context 用量） | WorkBuddy 无此工具，用上下文长度自我感知；进 danger zone 时按"每轮都写盘"处理 |

`assets/*.md` 缺失 → 跳过 `cp assets/*.md ./`；`./scripts/security-audit.sh` 缺失 → 用本机的 skills 安全审计流程替代。

## 与已装 skill 的分工

本机已有 `ixhlink-skills-self-improving`（捕获心得/错误/纠正、持续改进）。分工：

- **self-improving** = 记什么（学习条目沉淀）
- **proactive-agent** = 什么时候记、怎么不丢（WAL 先写后答、danger-zone buffer、压缩后恢复、主动追问）

两者可并存；重叠部分是"捕获纠正"，以 self-improving 的落点为准，避免双写。

## 触发

用户说"用 proactive agent / 先写后答 / WAL / 上下文快满了 / 接着上次继续"时加载本 skill。
