---
name: wechat-to-chatlab
description: 把本地微信(4.x)某个群聊或私聊的聊天记录与媒体(图片/视频)导出，并导入 ChatLab 查看。当用户想把微信聊天记录迁移/备份到 ChatLab、导出群聊或单人会话消息为可导入格式、或连同解密图片视频一起整理时使用。触发词：导出微信到 ChatLab、微信聊天记录导入 ChatLab、wechat to chatlab、微信备份到 ChatLab、导出私聊。
slug: wechat-to-chatlab
version: 1.3.0
displayName: 微信聊天记录导出并导入 ChatLab
---

# WeChat → ChatLab 导出导入

把本地微信 4.x（xwechat，Weixin.exe）某个**群聊或个人私聊**的**文字消息**导出为 ChatLab 可识别的
echotrace JSON，可选地**解密导出图片/视频**到本地画廊，最后用 ChatLab 官方 CLI (`clb import`)
**无界面导入**——不需要开窗口、不需要双击 `.cmd`。

## 适用场景

- 把微信群聊 / 单人私聊备份迁到 ChatLab 浏览
- 导出文字消息（含名片、位置、小程序/链接卡片、转账等类型渲染）
- 连同聊天图片（自动解密 V2 离线加密 + wxgf 转码）和视频（已下载的 mp4 正文）一起整理成离线画廊
- 免 GUI 直接写库导入，导入后可用 ChatLab MCP 让 AI 查询

## 前置条件

1. **已安装 `wechat-cli` 技能并完成密钥提取**：本技能复用它的 `wcdb_key_tool_windows`
   解密原语与 `zstandard`。产物在 `~/.wechat-cli/all_keys.json`。
2. **微信 4.x 已登录过**（只需密钥已提取，导出时不必在线）。
3. **ChatLab CLI 已安装**：`npm i -g chatlab-cli`（提供 `clb` 命令与 `clb import`/`clb mcp`）。
   桌面版 ChatLab 可选，仅用于「导入后浏览」。
4. **Windows 环境**：图片 wxgf 转码依赖 `VoipEngine.dll`；视频转码依赖 `ffmpeg`（可选）。
5. **依赖 Python 包**：`zstandard`、`cryptography`、`Pillow`（用托管解释器
   `C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe`）。

> **Node 版本必须与 better-sqlite3 匹配。** `chatlab-cli` 依赖原生模块 `better-sqlite3`，
> 它按安装时那个 Node 版本编译（本机全局安装在 **Node 24 / ABI 137**）。单个 clb 只能被
> 编译它的那个 ABI 的 node 加载，所以导入脚本按 **(node, clb) 成对**探测与尝试。
>
> **已实测的坑（2026-10-22）**：clb 0.37.5 在系统 **Node 24.20.0** 上 `import` 会在
> 「parsing 100%」之后原生断言崩溃（`RemoveEnvironmentCleanupHook ... Assertion failed: (env) != nullptr`，
> exit 134），stdout 拿不到 JSON 信封，看上去很像 ABI 问题但 better-sqlite3 本身开库正常。
> 遇到就装一份别的 ABI 的副本：
>
> ```bash
> "$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-to-chatlab/scripts/setup_alt_clb.py" --node-major 22
> ```
>
> 默认装到 `~/.chatlab/clb-node22`（不碰全局安装），装好后 `import_chatlab.py` 会自动发现并优先用它。

### 账号相关常量（可能需按账号修改）

- 图片离线解密密钥 = `md5(f"{ACCOUNT_CODE}{WXID}")[:16]`，XOR 密钥 = `ACCOUNT_CODE & 0xFF`。
- `WXID` 默认从数据目录名 `<wxid>_<rand>` 自动取前缀；`ACCOUNT_CODE` 是账号固定码，当前为 `14682585`。
  换账号迁移时若图片解不出，先确认这两个常量。

## 三步流程

### 第 1 步：导出文字消息为 ChatLab JSON

```bash
PY="C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-to-chatlab/scripts/export_to_chatlab.py" \
      "<群名/联系人备注关键词 或 完整@chatroom ID>" [输出目录 或 输出json]
```

**产物默认按日期命名**：`<会话名>_chatlab_<YYYY-MM-DD>.json`。第二参数给**目录**时写
`<目录>/<上述文件名>`；给具体 `.json` 时按你给的名字写（老用法）；省略则落在当前目录。
同一天重复导出会覆盖当天那份，前一天那份保留 → 天然按天归档。

- 关键词先按**群**匹配（`username LIKE '%@chatroom%'` 且备注/昵称命中），列候选并选命中的；
  一个群都没命中时**自动回退到私聊联系人**（备注 > 昵称 > 微信号），此时按 `Msg_<md5(wxid)>` 取表。
  传完整 `xxx@chatroom` 则直接精确命中该群。
- 输出 `echotrace` 结构：`{"chatInfo":{...},"session":{...},"messages":[{senderUsername, senderDisplayName, createTime, type, content, isSend}, ...]}`。
- 自动跨全部 `message_N.db` 合并去重、解析发言人显示名（备注>昵称>wxid）、渲染 appmsg 卡片。
- **`session` 字段不是随便写的**：ChatLab 导入 echotrace 时复用 WeFlow 解析器，会话名/类型只认
  `session.type`（中文 `"群聊"` / `"私聊"`）、`session.wxid`（不以 `@chatroom` 结尾→private）、
  `session.displayName || session.nickname`。写成 `session.chatType` 会被落成 `type=group`，
  且名字退化成**导入文件名**（带 `_ChatLab` 后缀）。脚本已按正确字段输出。
- 每次导出都会把「会话 → 当天、最后一条消息时间、条数、文件路径」记进
  `~/.chatlab/_wx_export_state.json`，下次导出会打印**相比上次新增多少条**，供导入前心里有数。

例：

```bash
"$PY" ".../export_to_chatlab.py" "夸夸" ./exports          # → ./exports/大佬夸夸群~_chatlab_2026-10-22.json
"$PY" ".../export_to_chatlab.py" "李嘉杰-电网"              # 私聊，落在当前目录
"$PY" ".../export_to_chatlab.py" "夸夸" 老名字.json         # 显式文件名，向后兼容
```

### 第 2 步（可选）：导出媒体（图片/视频）

```bash
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-to-chatlab/scripts/export_media.py" \
      "<群名关键词 或 @chatroom ID>" [输出目录]
```

- 图片：递归扫描 `msg/attach/<md5(群)>/*/Img/*.dat`，解密 V2 离线加密；`wxgf` 调 `VoipEngine.dll`
  转码为 jpg/png；PIL 校验有效性，优先 HD>显示版>缩略。
- 视频：扫描 `msg/video` 的 `*.mp4` 与 `*_thumb.jpg`，按消息 XML 的 `length`（字节数）精确配对；
  **仅本机已点开下载过的 mp4 才会存在**，未下载的只导出封面缩略图。
- 产出：`<输出目录>/images/`、`videos/`、`manifest.json`、`gallery.html`（自包含 base64 画廊）。

### 第 3 步：无界面导入 ChatLab（默认走 clb，不需要 GUI / cmd）

```bash
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-to-chatlab/scripts/import_chatlab.py" \
      <第1步的json路径> [--dry-run] [--data-dir DIR] [--session-id ID] [--new]
```

**默认就是增量**：同一个微信会话第二次导入时，脚本自动认出它上次落库的那个 ChatLab 会话，
带上 `--session-id` 合并进去，只补新消息、不建第二个会话。日常用法就是
「每天导出一次 → 再跑一次导入」，文件按天各存一份、数据永远是同一个会话。

增量目标的查找顺序：

1. `--session-id ID`（手工指定，优先级最高）
2. `~/.chatlab/_wx_import_map.json` 里记的该会话 `sessionId`（会先校验库里还在，删了就往下走）
3. 库里同名会话（比对 `session.displayName` 和导入文件名，带 `_chatlab_YYYY-MM-DD` 后缀会自动剥掉）
4. 都没有 → 新建

脚本做的事：

1. 校验 JSON 是 echotrace 结构（`session` + `messages`），会话名按
   `session.name → displayName → nickname → chatInfo.name` 依次取。
2. 定位 `chatlab-cli`：可能有**多份不同 ABI 的副本**（全局一份 + `~/.chatlab/clb-node*/`），
   与每个副本 ABI 匹配的 node 组成 `(node, clb)` 候选对。
3. **先探活**：用 `sessions list` 逐对试，跳出第一个真能跑通的组合（部分 node 能加载
   better-sqlite3 却让 clb 原生崩溃，光靠 ABI 探测分不出来）。
4. 数据目录优先级：`--data-dir` > `$CHATLAB_DATA_DIR` > `~/.chatlab/data`。
5. **过门槛**：`<data>/databases` 为空时 `clb` 会直接拒绝导入（连 `--dry-run` 都不给跑），
   脚本临时放一个占位库，结束后自动删除（只删自己创建的那个）。
6. **增量判定**：按上面 4 步找目标会话，命中就打印「增量导入 → 复用已有会话 xxx」并带
   `--session-id` 过去；没命中才新建。
7. 跑 `clb import --json`，逐行解析 JSON 信封（stdout 里混有 `[Parser V2]` 日志），
   打印会话 ID / 写入条数 / 去重条数 / 导入模式（`incremental` 或 `created`）/ 数据库路径。
   若某组合崩溃（断言 / abort / exit 134），自动清理残留锁并换下一对。
8. 成功后将「会话 → ChatLab 会话 ID」写回 `~/.chatlab/_wx_import_map.json`，
   以后改备注名也不会错配。

常用参数：

| 参数 | 用途 |
|---|---|
| `--dry-run` | 只预检条数与格式，不写库 |
| `--data-dir DIR` | 指向别的数据目录（多套 ChatLab 数据时用） |
| `--session-id ID` | 手工指定目标会话（优先于自动判断） |
| `--new` | **强制新建**独立会话，即使已有同名会话（想留一份快照副本时用） |
| `--force` | 不自动复用会话，直接交给 clb 自行判断（一般也会增量去重） |
| `--gui` | 兜底：放弃 clb，改为生成 `import_to_chatlab.cmd` + 拉起桌面版 |
| `--timeout SEC` | 导入超时，默认 600 秒（超大群可调大） |

典型输出（增量补 1 条）：

```
[+] 增量导入 → 复用已有会话 chat_1792655057980_d299aaad「小鲜肉肉~」(739 条 / 5 成员)
    本次只补写新消息，重复内容由 clb 按内容去重；想另建一个独立会话请加 --new。
  写入消息  : 1
  重复跳过  : 739
  导入模式  : incremental /
```

### 第 4 步（可选）：把 ChatLab MCP 挂到 WorkBuddy，让 AI 直接查询

`clb mcp` 是官方 stdio MCP server。**不要在 `mcp.json` 里写死 node 路径**——升级 Node 或
`npm rebuild better-sqlite3` 后 ABI 一变就起不来。用安装脚本写，它指向 `mcp_launcher.py`：

```bash
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-to-chatlab/scripts/install_mcp.py" \
      [--data-dir DIR] [--dry-run]
```

它会：备份原 `mcp.json` → 写入/更新 `chatlab` 条目（保留其它 server）→ 用启动器做一次
真实 MCP 握手自检（打印 `serverInfo` 与工具数，正常是 19 个）。

写入的条目形如：

```json
"chatlab": {
  "type": "stdio",
  "command": "<你的 python.exe>",
  "args": ["<...>/scripts/mcp_launcher.py"],
  "env": { "CHATLAB_DATA_DIR": "C:\\Users\\Lenovo\\.chatlab\\data" }
}
```

`mcp_launcher.py` 每次被拉起时会**现场探活**（`sessions list`）挑出真正能跑的
`(node, clb)` 组合——既能绕开 ABI 不匹配，也能绕开「ABI 匹配但 clb 崩溃」的 Node 24 情形；
结果缓存到 `~/.chatlab/.clb_pair_cache.json`（按 chatlab-cli 的 mtime 失效）。挑中后把
stdin/stdout/stderr 原样透传给 `node chatlab.mjs mcp`。
所以 Node 升级、`npm rebuild`、换机器都不需要改配置；缓存出问题就删掉那两个 `.clb_*.json`。

启用后仍需手动信任一次：**连接器管理 → 右上角「自定义连接器」→ chatlab → Trust**。

## 重要注意事项 / 已知限制

- **ChatLab 不存媒体二进制**：导入后图片/视频在 ChatLab 内只显示 `[图片]`/`[视频]` 占位符。
  要看真实媒体请用第 2 步的 `gallery.html`（按 md5 对照消息时间线查看）。
- **视频正文需先点开**：微信默认只缓存封面，mp4 正文要用户在微信里点开过才会落盘。
- **`clb validate` 会误报**：它按严格 `chatlab` schema 校验，对 echotrace 格式会报上万条错误。
  **这不影响 `clb import`**（import 走格式自动识别，输出里会显示 `ycccccccy/echotrace 导出`）。
- **重复导入不会产生重复会话**：默认自动复用原会话 ID 增量合并，第二次导入通常 `写入 0 / 重复 N`
  或只写入新增的那几条。真要建第二个会话必须显式加 `--new`。
- **群级系统消息会被跳过**（如「XXX 邀请 YYY 进群」），避免 ChatLab 解析丢弃整条。
- **消息可能跨多个 message_N.db**：脚本已遍历全部库合并去重，单库读取会静默截断。
- **发言人解析不到时归到「我」**：红包/转账等系统型消息常无明确发言人。
- **隐私**：全部本地处理，不上传任何数据。

## 文件布局

```
wechat-to-chatlab/
├── SKILL.md
├── .bak_20261022/            # 支持私聊+崩溃回退改造前的原始脚本备份
└── scripts/
    ├── _clb_common.py         # 公用：定位 clb 实例 / 挑 ABI 匹配的 node / 崩溃判定 / 残留锁 / JSON 信封
    ├── _state.py              # 公用：日期命名 + 导出状态 + 会话 ID 映射（增量导入靠它）
    ├── export_to_chatlab.py   # 第1步：文字消息(群聊或私聊) → ChatLab echotrace JSON
    ├── export_media.py        # 第2步：图片(解密)+视频(已下载) → 画廊
    ├── import_chatlab.py      # 第3步：clb import 无界面导入（默认增量合并，--gui 可退回 .cmd）
    ├── setup_alt_clb.py       # 踩坑时用：给别的 Node 大版本装一份隔离 clb（不碰全局）
    ├── mcp_launcher.py        # 第4步：MCP stdio 启动器（启动时动态挑 node，透传 stdio）
    └── install_mcp.py         # 第4步：把 chatlab 条目写进 ~/.workbuddy/mcp.json 并自检
```

## 增量备份状态文件

| 文件 | 内容 | 删了会怎样 |
|---|---|---|
| `~/.chatlab/_wx_export_state.json` | 每个会话当天导出到哪条消息、多少条、文件路径 | 只是看不到「比上次新增多少条」 |
| `~/.chatlab/_wx_import_map.json` | 每个微信会话对应的 ChatLab `sessionId` | 退化成按会话名匹配（改过名可能新建一个） |

想强制重来（比如想让某个会话重新走「新建」），删掉 `_wx_import_map.json` 里对应那一项即可，
**不要删 ChatLab 的 databases**。

## 故障排查

- `找不到 wechat-cli skill 的 scripts 目录`：先安装/启用 `wechat-cli` 技能。
- 图片大量 `fail` / 解不出：检查 `ACCOUNT_CODE` 与 `WXID` 是否匹配当前账号。
- `VoipEngine.dll` 缺失：确认微信安装路径，或改 `export_media.py` 里的 `DLL` 常量。
- `ffmpeg` 不存在：视频仍能导出原片与封面，仅跳过 H.264 转码。
- **导入时 clb 原生崩溃**（`Assertion failed: (env) != nullptr` / exit 134，stdout 没有 JSON 信封）：
  这是 Node 24 上的已知组合问题，不是数据问题。跑
  `python scripts/setup_alt_clb.py --node-major 22` 装一份独立副本，导入脚本会自动改用。
- **会话落成 `group`、名字带 `_ChatLab` 后缀**：JSON 的 `session` 没按 WeFlow 字段写。
  正确字段是 `type: "私聊"/"群聊"` + `wxid` + `displayName`（脚本已修，别用 `session.chatType`）。
- **`setup_alt_clb.py` 报「npm 报成功但目录里没有 chatlab-cli」**：目标目录在沙箱里不可写，
  换 `--dir <可写路径>` 或设 `CHATLAB_CLB_ALT_DIR`。
- `没有找到能真正使用 better-sqlite3 的 Node`：用装 `chatlab-cli` 时那个 Node 运行，
  或在该 Node 下 `npm rebuild better-sqlite3`；也可加 `--gui` 兜底走桌面版。
- `找不到 chatlab-cli 的入口 chatlab.mjs`：`npm i -g chatlab-cli`，
  或用 `CHATLAB_CLB_JS` 环境变量直接指定 `.mjs` 路径。
- `clb import` 报 `databases not found`：脚本已自动过门槛；若是手工调用，需保证
  `<data>/databases` 非空（放任意一个 `.db` 即可）。
- `--session-id` 指定错 ID：先用 `clb sessions list --format json` 查实际 ID；
  注意 `clb sessions list` 不接受 `--json`，要用 `--format json`。
- **MCP 起不来**：先直接手跑启动器看 stderr（它只往 stderr 写诊断，不污染 JSON-RPC）：
  `python scripts/mcp_launcher.py` 用管道喂一条 `initialize` 即可。常见原因是
  chatlab-cli 没装好 / `npm i -g chatlab-cli` 换了路径。
- **MCP 报了 ABI 错**：说明缓存或探测被绕过，删 `~/.chatlab/.clb_node_cache.json` 让它重探；
  仍不行就 `npm rebuild better-sqlite3`（用哪个 node 装的就用哪个 rebuild）。
- **想强制指定 node**：设环境变量 `CHATLAB_NODE=<node.exe 绝对路径>`（优先探测但仍会校验 ABI，
  不可用就自动回退）。同理 `CHATLAB_CLB_JS` 可绕过 chatlab-cli 的路径探测，
  `CHATLAB_CLB_ALT_DIR` 可指定副本目录。
- **导入锁残留**（`~/.chatlab/data/.chatlab-import.lock` 里是死 pid）：下次导入脚本会自动清；
  手工调用前也可直接删掉这个文件。
