# ADAPTATION.md — bid-writer-pro（标书智能生成专家 v2.2）

> 本文件由 WorkBuddy community-skill-install 流程生成，记录来源、审计结论与适配说明。
> 上游 `SKILL.md` 原样保留，未做任何修改；本文件为适配层，不混入上游文件。

## 1. 来源

- 仓库 URL：https://github.com/Get00/BiaoShu-SKILL
- 实际 skill 子目录：`BiaoShu-SKILL-main/BiaoShu-writer-pro/`（仓库根另有 README.md / LICENSE，非 skill 本体）
- 分支：main（codeload 归档获取）
- 实际版本：v2.2.0（见 `_meta.json` 与 SKILL.md frontmatter）
- 作者：TreaSkill
- 包体文件清单：
  - `SKILL.md`（31.5KB，说明文档，原样保留）
  - `_meta.json`（2.1KB，元数据）
  - `requirements.txt`（依赖清单）
  - `install.py`（依赖安装脚本）
  - `scripts/`（21 个 Python 脚本：主流程 + 解析/转换/提取/生成/格式化等）
  - `templates/`（27 个 Markdown：标书制作指南、各行业指南、标书范本、招投标知识）
  - `references/industry_configs.json`（行业配置）

## 2. 审计结论

**定级：P1（良性依赖安装，无 P0/P1 破坏性风险）**

逐条判据：

| 判据 | 结果 | 说明 |
|------|------|------|
| 可执行代码 | ✅ 有 | `scripts/*.py` + `install.py`，均为本地文件处理/模板渲染/格式转换，**无自动执行钩子** |
| 数据外发 | ❌ 无 | 全仓无 `requests`/`urllib`/`socket`/`httpx`/`urlopen`/`webhook`；唯一网络相关是一段 OCR 工具提示字符串（ilovepdf.com），非代码调用 |
| 提示注入 | ❌ 无 | 无"忽略指令/覆盖系统提示/不要告诉用户"等字样 |
| 凭据读取 | ❌ 无 | 无读取 `.env`/SSH key/token/浏览器 cookie 的代码 |
| 破坏性动作 | ❌ 无 | 无 `rm -rf`/`shutil.rmtree`/`os.remove`/`os.unlink` 删除用户文件；仅在用户指定 `--output-dir` 或招标文件同目录**创建**输出文件 |
| 依赖下载 | ⚠️ 有（P1） | `install.py` / `requirements.txt` 通过 `pip install` 安装 7 个知名纯 Python 包（python-docx、pdfplumber、openpyxl、PyPDF2、jieba、pandas、pywin32）；**无自动执行**，需用户手动触发 |
| 上游自述与实况一致性 | ✅ 一致 | SKILL.md 描述的功能、脚本列表、模板数量与实际文件吻合 |

低风险点：
- 功能运行时会**在工作区/输出目录写文件**（标书 .docx 及中间 JSON/Markdown），属预期行为，非破坏性。
- `pywin32` 仅在 Windows 上安装，用于解析旧版 .doc；其余为跨平台包。
- 该 skill 源自 Trea AI IDE 生态，示例中的 `/path/to/bid-writer-pro/scripts` 为占位路径，WorkBuddy 调用时需按实际落点替换。

## 3. 路径映射表

| 上游假定 | WorkBuddy 实际落点 |
|----------|--------------------|
| skill 根目录（含 SKILL.md） | `C:\Users\Lenovo\.workbuddy\skills\bid-writer-pro\` |
| `scripts/` 调用示例中的 `/path/to/...` | `C:\Users\Lenovo\.workbuddy\skills\bid-writer-pro\scripts\` |
| `templates/` 行业指南 | `C:\Users\Lenovo\.workbuddy\skills\bid-writer-pro\templates\` |
| 输出目录（默认与招标文件同目录 / `--output-dir`） | 由用户每次运行指定，落在当前工作区 |
| 上游提到的专属工具（如 session_status） | 无；本 skill 不依赖 WorkBuddy 特殊工具，纯 Python 脚本 |

依赖安装提示：首次使用前需在其 `scripts/` 目录运行
`python install.py --auto` 或 `pip install -r requirements.txt`。
注意环境 Python 选择（本机优先用托管 3.13：`C:\Users\Lenovo\.workbuddy\binaries\python\versions\3.13.12\python.exe`），避免落到 3.14 缺轮子。

## 4. 与已装 skill 的分工

- 本机已装 skills 目录：`C:\Users\Lenovo\.workbuddy\skills\`（含 community-skill-install 等）。
- `bid-writer-pro` 是**独立的文档生成类 skill**，与现有 skill 无功能重叠，不存在双写风险。
- 若后续安装其他"文档/Word 生成"类 skill，需注意命名与功能区分。
