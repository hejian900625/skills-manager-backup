---
name: wechat-cli
description: 通过 wechat-cli 读取和分析微信聊天记录。当用户想查看、搜索、导出或分析微信消息、联系人、收藏时调用此技能。
slug: wechat-cli
version: 1.0.1
displayName: 通过 wechat-cli 读取和分析微信聊天记录
---

# WeChat CLI — 微信聊天记录读取与分析

本技能通过 `wechat-cli` 命令行工具，帮助用户读取和分析本地微信的聊天记录、联系人、收藏等数据。支持会话浏览、消息搜索、聊天记录导出、统计分析等功能。

## 适用场景

- 查看最近会话列表 / 未读消息
- 查看指定联系人或群聊的聊天记录
- 按关键词搜索消息
- 导出聊天记录为 Markdown 或纯文本
- 聊天统计分析（消息数量、活跃度等）
- 查看微信收藏
- 获取增量新消息（断点续传）
- 对聊天记录进行分类总结、重点提取等分析任务

## 前置条件

### 系统支持
- Windows（Weixin.exe）
- macOS（WeChat）
- Linux（wechat）

### 必须满足
1. **使用指定版本的微信** — wechat-cli 仅兼容微信 4.0+ 新版架构，不支持 3.x 旧版。本 skill 附带了指定版本的微信安装包，详见下方"微信安装"
2. **微信客户端已安装并登录** — 工具读取本地微信数据库，微信必须已登录
3. **初始化时微信必须处于运行状态** — 密钥提取需要扫描微信进程内存
4. **Python 3.10+** — wechat-cli 是 Python 工具

### 微信安装（重要）

wechat-cli **仅支持微信 4.0 及以上版本**，不支持微信 3.x 旧版。

**为什么需要 4.0+：**
- 微信 4.0 采用了全新的跨平台架构，进程名从 `WeChat.exe` 变为 `Weixin.exe`（Windows），数据目录从 `WeChat Files` 变为 `xwechat_files`
- wechat-cli 的密钥提取逻辑针对 4.0 架构设计，无法识别 3.x 版本的进程和数据库

本 skill 附带了以下微信安装包（与 skill 目录同级）：

| 平台 | 文件 | 版本 | 说明 |
|------|------|------|------|
| Windows | `WeChatWin-4.0.1.30.zip` | 4.0.1.30 | 免安装绿色版，解压即用 |
| macOS | `WeChatMac-4.1.8.dmg` | 4.1.8 | DMG 安装镜像 |

#### Windows 安装指引

1. **解压安装包**：将 `WeChatWin-4.0.1.30.zip` 解压到任意目录（如 `C:\WeChat`）
2. **运行微信**：进入解压目录，双击 `Weixin.exe` 启动微信
3. **扫码登录**：用手机微信扫码登录
4. 确认微信已完全启动并登录后，再执行 `wechat-cli init`

> Windows 版本是免安装绿色版，无需运行安装程序，解压后直接双击 `Weixin.exe` 即可使用。

#### macOS 安装指引

**第一步：安装微信**

1. **打开 DMG 文件**：双击 `WeChatMac-4.1.8.dmg`，系统会挂载一个磁盘镜像
2. **安装微信**：在弹出的窗口中，将左侧的 **WeChat** 图标拖拽到右侧的 **Applications（应用程序）** 文件夹
3. **弹出 DMG**：安装完成后，在 Finder 侧边栏点击 DMG 磁盘旁的弹出按钮，卸载镜像

**第二步：重新签名 WeChat（必须）**

macOS 默认禁止读取其他进程内存，需要对微信进行 ad-hoc 重签名，wechat-cli 才能提取密钥。

1. **打开终端**：在「启动台」搜索「终端」或「Terminal」并打开
2. **提取微信原有权限**：
```bash
codesign -d --entitlements - --xml /Applications/WeChat.app > ~/wechat_ent.plist
```
3. **复制 WeChat 到用户目录**（推荐，最安全）：
```bash
rm -rf ~/Applications/WeChat.app
cp -R /Applications/WeChat.app ~/Applications/
```
4. **对副本进行签名**：
```bash
codesign --force --deep --sign - --entitlements ~/wechat_ent.plist ~/Applications/WeChat.app
```
5. **以后运行这个副本**：
```bash
open ~/Applications/WeChat.app
```

**第三步：登录并初始化**

1. **打开微信**：运行上一步签名后的副本（`~/Applications/WeChat.app`）
2. **处理安全提示**：首次打开可能提示"无法验证开发者"或"来自身份不明的开发者"：
   - 点击 **取消**
   - 进入 **系统设置 → 隐私与安全性**，找到关于 WeChat 的安全提示，点击 **仍要打开**
   - 再次打开 WeChat，点击 **打开**
3. **扫码登录**：用手机微信扫码登录
4. 确认微信已完全启动并登录后，执行初始化：
```bash
sudo wechat-cli init --force
```

> **为什么需要重新签名？** macOS 出于安全考虑，禁止进程读取其他进程的内存。wechat-cli 需要扫描微信进程内存来提取数据库解密密钥，因此必须对微信进行 ad-hoc 重签名以放开此限制。
>
> **注意**：微信更新后需要重新签名。每次微信自动更新后，重复上述第二步即可。

#### 已安装旧版微信怎么办？

如果电脑上已经安装了旧版微信（3.x），需要先卸载或退出旧版，再安装上述指定版本。Windows 绿色版无需卸载原有微信，但建议退出正在运行的旧版微信后再启动新版。

> **重要**：必须使用附带的指定版本微信。其他版本（即使也是 4.0+）可能因架构差异导致密钥提取失败。

## 安装

```bash
pip install wechat-cli
```

依赖包（自动安装）：`click`、`pycryptodome`、`zstandard`

安装完成后验证：
```bash
wechat-cli --version
# 输出: wechat-cli, version 0.2.4
```

## 初始化（首次使用必读）

初始化会提取微信数据库的加密密钥并生成配置文件。**只需执行一次**。

### 步骤

1. **确保微信正在运行且已登录**（这是必须的，密钥从微信进程内存中提取）

2. **执行初始化命令**：
```bash
wechat-cli init
```
工具会自动：
- 检测微信数据目录
- 扫描微信进程内存提取数据库密钥
- 在 `~/.wechat-cli/` 下生成 `config.json` 和 `all_keys.json`

3. **如果自动检测失败**，手动指定数据目录：
```bash
wechat-cli init --db-dir "C:\path\to\db_storage"
```

### 微信数据目录位置参考

| 系统 | 默认路径 |
|------|----------|
| Windows | `%APPDATA%\Tencent\xwechat\config\*.ini` 指向的目录下 `xwechat_files\<wxid>\db_storage` |
| macOS | `~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/<wxid>/db_storage` |
| Linux | `~/Documents/xwechat_files/<wxid>/db_storage` |

> **提示**：`<wxid>` 是你的微信内部 ID，类似 `wxid_xxxxxxxxxxxxx`。

### 重新初始化

如果密钥过期（如微信更新后），强制重新提取：
```bash
wechat-cli init --force
```

### 配置文件说明

初始化后，配置保存在 `~/.wechat-cli/` 目录：

| 文件 | 说明 |
|------|------|
| `config.json` | 主配置，记录 `db_dir`（数据库路径） |
| `all_keys.json` | 数据库解密密钥 |
| `last_check.json` | `new-messages` 命令的状态文件（记录上次读取位置） |

## 快速入门

### 1. 查看最近会话
```bash
wechat-cli sessions
```

### 2. 查看某人的聊天记录
```bash
wechat-cli history "张三" --limit 20
```

### 3. 搜索消息
```bash
wechat-cli search "关键词"
```

### 4. 查看未读会话
```bash
wechat-cli unread
```

### 5. 导出聊天记录
```bash
wechat-cli export "张三" --format markdown --output chat.md
```

## 命令总览

| 命令 | 说明 | 常用参数 |
|------|------|----------|
| `init` | 初始化（提取密钥） | `--db-dir`, `--force` |
| `sessions` | 最近会话列表 | `--limit`, `--format` |
| `history` | 指定聊天的消息记录 | `--limit`, `--offset`, `--start-time`, `--end-time`, `--type`, `--media` |
| `search` | 搜索消息内容 | `--chat`, `--start-time`, `--end-time`, `--limit`, `--type` |
| `contacts` | 搜索/列出联系人 | `--query`, `--detail`, `--limit` |
| `export` | 导出聊天记录 | `--format`, `--output`, `--start-time`, `--end-time`, `--limit` |
| `members` | 群聊成员列表 | `--format` |
| `stats` | 聊天统计分析 | `--start-time`, `--end-time`, `--format` |
| `unread` | 未读会话 | `--limit`, `--format` |
| `new-messages` | 增量新消息 | `--format` |
| `favorites` | 微信收藏 | `--type`, `--query`, `--limit`, `--format` |

> 完整命令参数详见 `references/commands.md`

## 输出格式

大多数命令支持 `--format` 参数：
- `json`（默认）— 结构化 JSON，适合程序处理
- `text` — 纯文本，适合人类阅读

时间格式：`YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM:SS`

消息类型过滤（`--type`）：`text`、`image`、`voice`、`video`、`sticker`、`location`、`link`、`file`、`call`、`system`

## 重要注意事项

- **默认限制**：`history` 默认返回 50 条，`search` 最大 500 条，`sessions` 默认 20 个。导出大量数据时用 `--limit 100000`
- **系统占位会话**：`brandsessionholder`、`@placeholder_foldgroup` 是系统占位符，导出时会失败，属正常现象
- **隐私安全**：所有数据仅在本地处理，不会上传任何信息
- **微信需运行**：虽然查询操作不需要微信运行，但初始化（密钥提取）必须微信在线

## 分析工作流

当用户需要分析聊天记录时，推荐工作流详见 `references/analysis-guide.md`。

典型流程：
1. `sessions` — 浏览会话列表，确定分析对象
2. `history` — 读取目标聊天的消息记录
3. 对消息内容进行分类、总结、提取重点
4. 如需深度分析，用 `stats` 获取统计数据辅助

## 故障排查

常见问题及解决方案详见 `references/troubleshooting.md`。

## 微信 4.1.12+ 密钥提取（重要适配，2026-08-10 实测）

> **背景**：微信 4.1+ 不再在进程内存缓存明文密钥（`x'...'` 格式），`wechat-cli init` 的内存扫描在 4.1+ 上 0 命中属正常。wx_key（DLL 注入工具）已被 DMCA 下架，GitHub release 全删。实测发现：**4.1.12 的 `com.Tencent.WCDB.Config.Cipher` 对象里存的是每个数据库的（派生后密钥 32B + salt 16B）十六进制对，密钥可直接用于解密，无需 PBKDF2**。

### 前提
- 微信 4.1.12+ 正在运行且已登录
- **必须确认当前登录账号与目标 db_storage 目录一致**（多开/多账号环境：内存里的密钥属于当前登录账号！用 `check_account` 逻辑扫描内存中 `wxid_xxx` 出现次数确认）
- Python 环境（本机：`C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe`）

### 步骤
1. **扫描并 dump Config.Cipher blob**（脚本内改 DB_DIR 为目标账号目录）：
   ```
   python scripts/dump_config_blobs.py
   ```
   产出 `C:/Users/Administrator/AppData/Local/Temp/config_dump/blob_*.bin`
2. **提取密钥并生成配置**（脚本内改 DB_DIR）：
   ```
   python scripts/gen_keys.py
   ```
   自动对 blob 中所有 64~192 hex 串取 32B 窗口，用 HMAC 校验匹配数据库 salt，生成 `~/.wechat-cli/all_keys.json` + `config.json`
3. **验证**：
   ```
   wechat-cli sessions --limit 5 --format text
   ```

### 已知限制
- 实测 16/18 库成功；`message\weclaw.db`、`solitaire\solitaire.db` 未提取到（非核心库，不影响聊天记录查询）
- 微信重启/更新后密钥可能变化，需重新执行上述步骤
- 若 Config.Cipher 扫描 nodes=0：微信版本过新或进程选择错误，先确认登录账号
- 密钥对是 (key+salt)，**直接当加密密钥用，不要做 PBKDF2 派生**（那是 4.1.x 早期版本的 passphrase 路线）

---

## 微信 4.1.13+ 密钥提取（XOR 解码路线，2026-09-29 实测 21/21 成功）

> **重要修正**：上面"微信 4.1.12+ 密钥提取"章节所述路线在 **微信 4.1.13.65** 上**会失败**
> （实测：直接当密钥用 → 0/21；PBKDF2 派生 → 0/21）。原因是漏了 XOR 解码步骤。
> 本技能 `scripts/` 下的三个脚本已于 2026-09-29 **全部重写为参数化 + 带 XOR 解码**，可直接用。

### 真正结构

`Config.Cipher` 的 memcpy blob（99 字节）**不是明文**，而是被 XOR 混淆的 ASCII 字符串：

```
XOR_MASK = d2c7442458020000004889442450488b450048844c2448488944254048584c24
解密后   = x'<enc_key 64 hex><salt 32 hex>'      (99 字节 = 3 + 96)
```

- blob 前 2 字节固定 `aae0`、末字节固定 `63`（XOR 掩码循环特征，可作快速识别）
- **前 32 字节（64 hex）直接就是 SQLCipher 的 AES-256 密钥**
- **不需要 PBKDF2**（PBKDF2 是 4.1.x early 的 passphrase 路线，4.1.13 已不用）

### 推荐用法：一步到位

```bash
python scripts/extract_keys.py --db-dir "<db_storage>" --out ~/.wechat-cli/all_keys.json
```

完整链路：枚举 Weixin.exe 进程 → 定位 Config.Cipher 节点 → dump blob → XOR 解码 →
正则取 (key, salt) → HMAC 校验 → 写 `all_keys.json` + `config.json`。
`--db-dir` 省略时自动从微信 ini 配置检测。实测 21/21 通过。

### 分步用法（blob 已 dump 到磁盘、想离线解析时）

```bash
# 1. dump blob 到磁盘
python scripts/dump_config_blobs.py --db-dir "<db_storage>" --dump-dir "%TEMP%/config_dump"

# 2. 离线解析生成密钥
python scripts/gen_keys.py --db-dir "<db_storage>" --blob-dir "%TEMP%/config_dump"
```

### 多账号切换

```bash
python scripts/switch_account.py            # 列出本机发现的账号及密钥状态
python scripts/switch_account.py 1          # 切换到账号 1（也支持传账号名）
python scripts/switch_account.py --add "<db_storage 路径>"   # 手动登记账号
```

账号自动从 `%APPDATA%/Tencent/xwechat/config/*.ini` 推导的数据根下扫描
`xwechat_files/*/db_storage`，不再硬编码路径。每个账号密钥存为
`~/.wechat-cli/all_keys_account<N>.json`，切换即复制为 `all_keys.json` 并更新 `config.json`。

### 验证

```bash
python scripts/wcdb_key_tool_windows.py decrypt \
  --db-dir "<db_storage>" --keys ~/.wechat-cli/all_keys.json --output <out_dir>
```

解密后应用 sqlite3 打开，能读到 `SessionTable`/`contact`/`Msg_xxx` 表即成功。

### 踩坑记录（改脚本时务必注意）

- `VirtualQueryEx` 的参数顺序是 `(hProcess, lpAddress, lpBuffer, dwLength)`，
  **buffer 在长度之前**。顺序写反不会报错，而是直接返回 0 区域 → needle hits 全 0。
- `all_keys.json` 里的路径键用**反斜杠**（`favorite\favorite.db`），
  用正斜杠去查会静默返回 `NO KEY`。
- 微信 4.1.13 实测：19 个库能匹配，多出 2 个库（`message_1.db` 等）也在 21 个里全中；
  若某库始终 MISSING，先确认该库是否属于当前登录账号。


---

## 消息查询（wechat-cli 不可用时：直读 SQLite）

> **PyPI 上没有 `wechat-cli` 这个包**（`https://pypi.org/pypi/wechat-cli/json` 返回 404），
> 所以 `pip install wechat-cli` 一定失败。查询走直读解密库。

关键映射链路：

1. **群/联系人定位** → `contact/contact.db`
   ```sql
   SELECT username, nick_name, remark FROM contact WHERE nick_name LIKE '%群名%';
   ```
2. **群在哪个消息库** → 各 `message_N.db` 的 `Name2Id`
   ```sql
   SELECT rowid, user_name FROM Name2Id WHERE user_name = '<xxx@chatroom>';
   ```

   > ⚠️ **一个群的消息会跨多个 `message_N.db`，必须遍历全部并合并！**（2026-09-29 踩坑）
   >
   > 实测：`message_1.db` 只有 1 张 Msg 表（1.2MB），装 2026-02~08-22 的 1955 条；
   > `message_0.db` 有 485 张 Msg 表（199MB），装 08-27~09-29 的 849 条。
   > 只读探测到的第一个库 → **记录会静默截断在某个日期**，且不报错。
   >
   > 微信按活跃度把同一会话的历史切分到不同库，**同一群表名在各库中相同**。
   > 正确做法：对 `message/*.db` 全部解密，凡含该 `Msg_<md5>` 表的都取，再按
   > `(server_id, local_id)` 去重后按 `create_time` 排序。
   > 去重前先验证两库无交集（实测本机 1955+849 零重叠）。

3. **消息表名** = `'Msg_' || md5(username)`（**不是**用 rowid）
   - 例：`md5('3555834173@chatroom')` = `2c6325591cad328f6a791c10a18e1b3f` → 表 `Msg_2c6325591cad328f6a791c10a18e1b3f`
4. **消息表字段**：`local_id, local_type, real_sender_id, create_time, message_content, WCDB_CT_message_content`
   - `real_sender_id` → 同库 `Name2Id.rowid` → user_name → `contact` 表取 remark/nick_name
   - `create_time` 是 Unix 秒
5. **内容解压**：`WCDB_CT_message_content == 4` 时 `message_content` 是 zstd 压缩的 bytes
   ```python
   zstandard.ZstdDecompressor().decompress(v).decode('utf-8','replace')
   ```
   - 群聊文本消息形如 `wxid_xxx:\n实际内容`，需按 `:\n` 切分取正文
   - `local_type`：1=文本 3=图片 34=语音 43=视频 47=表情 48=位置 42=名片 10000=系统

6. **用 WAL 取最新增量**：主库解密后可能缺最新几条（还在 `-wal` 里未 checkpoint）。
   `...-wal` 可达 4MB 且持续增长。若要`今天`级别的完整性，先让微信退出或用
   `sqlite3` 以只读方式带 wal 打开。一般分析场景主库已足够。

完整可用实现：见本技能 `scripts/wx_export_group.py`（多库合并 + 去重 + 渲染）。

### 环境注意

- **必须用带 `zstandard` 的解释器**：`C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
  系统 `3.13.12` 裸解释器**没有** zstandard，会静默退化为不解压 → 内容变乱码。
- 解密函数可直接复用：`scripts/wcdb_key_tool_windows.py` 的 `_decrypt_database(db_path, out_path, enc_key)`，
  或 `_decrypt_page`。前提是 `enc_key = bytes.fromhex(keys['message\\message_0.db']['enc_key'])`。

---

## 收藏查询（favorite.db，2026-09-29 实测 606 条全量导出）

解密 `favorite\favorite.db` 后可读，表结构：

| 表 | 说明 |
|----|------|
| `fav_db_item` | 收藏条目主表（`local_id, type, update_time, content, fromusr, realchatname, ext_buf`） |
| `fav_tag_db_item` | 标签定义（`local_id, name`） |
| `fav_bind_tag_db_item` | 条目↔标签绑定（**字段名是 `fav_local_id`，不是 `item_local_id`**） |
| `favorite_fts.db` 的 `fav_fts_v1*` | 全文索引（606 行，可用于关键词搜索） |

### 关键点

1. **`content` 是 XML 字符串**，根节点 `<favitem type="N">`，需用**宽容解析**（`html.parser`）
   而非 `ET.fromstring`——微信的 XML 常有不闭合/裸 `&`，严格解析会抛异常。
2. **`update_time` 是 Unix 秒**。
3. **标题字段因类型而异**，取值优先级：
   - 链接(5)：`<pagetitle>` + `<link>`/`<weburl>`/`<clean_url>` + **`<pagedesc>`**
   - 文本(1)：`<desc>`
   - 文件(8)：`<datalist><dataitem><datatitle>`（`<title>` 是 `favitem` 上的文件名）
   - 聊天记录(14)：`<title>`（如"Yugi和Xiu的聊天记录"）+ `<datadesc>`（内含 `&#x0D;&#x0A;` 需 HTML 反转义）
   - 位置(6)：`<locitem>` 的 `label`/`poiname`/`lat`/`lng`
   - 笔记(18)：`<datadesc>` + `<locitem>`
   - 媒体类(2 图片 / 3 语音 / 4 视频 / 16 短视频 / 7 音乐)：**只有 CDN key，无文字标题**，属正常

   > ⚠️ **链接类的摘要是 `<pagedesc>`，不是 `<desc>`**（2026-10-10 踩坑）。
   > 只抓 `desc` 会得到「374 条链接全部无摘要」的错误结论，实际 315 条有摘要。
   > 链接类还有 `<appmsgshareitem><srcdisplayname>` = 公众号名（213/374 条有），
   > `<brandid>` = 品牌 id，`<clean_url>` = 去跟踪参数的干净链接。

4. **type 枚举**（实测）：1=文本 2=图片 3=语音 4=视频 5=链接 6=位置 7=音乐 8=文件 14=聊天记录 16=短视频 18=笔记
5. 媒体文件本体不在 db 内，只存 `cdn_dataurl`/`cdn_datakey` 和数据目录路径。
6. **WAL 已自动包含**：实测主库解密后条数与"WAL 拼接版"一致（613 条，最新到当日 09:58），
   收藏库不需要像message 库那样额外处理 WAL 增量。

### 导出命令

```bash
PY="C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
DB="D:/WorkBuddy/2026-09-29-14-04-17/wx_decrypted2/favorite/favorite.db"

# 全量（613 条，含所有类型）
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts/wx_export_favorites.py" --db "$DB" --out wx_export

# 只导链接/文章（type=5，374 条），带年份/平台/公众号/域名聚合 + 主题分析
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts/wx_export_favorites_links.py" \
      --db "$DB" --out wx_export [--year 2026] [--domain zhihu]
```

`wx_export_favorites_links.py` 产出 `wx_export/微信收藏_链接文章.md`：
年份分布 / 平台分布 / 域名 TOP / 公众号 TOP / 标签分布 / 明细索引 / 主题聚类 / 完整条目（含摘要+链接）。

> ⚠️ 若 `wx_decrypted2/` 里的库是旧的，先重新解密再导：
> ```python
> W._decrypt_database(src, tmp, bytes.fromhex(keys["favorite\\favorite.db"]["enc_key"]))
> ```

---

## 全部群聊基本信息导出（不含聊天记录，2026-10-10 实测 541 群）

```bash
PY="C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts/wx_export_groups.py" \
      --out wx_export [--active-only] [--min-members 100]
```
→ 产出 `wx_export/微信群聊_基本信息.md`（规模分布 / 活跃度分布 / 群主 TOP / 群列表 / 公告摘录）

### 群元数据的 6 个来源

| 字段 | 来源 | 说明 |
|---|---|---|
| 群名 | `contact.nick_name`（fallback `remark`） | |
| 群 ID | `contact.username` | 形如 `xxx@chatroom` |
| **成员数** | `chatroom_member` 按 `room_id` 分组计数 | **`room_id` 是 `contact.id`（整数），不是 username** |
| 群主 | `chat_room.owner` → contact 表查昵称 | `chat_room.username` = 群 ID，`chat_room.id` = contact.id |
| 群公告 | `chat_room_info_detail.announcement_` | 字段带**尾下划线**；`room_id_` 同样是 contact.id |
| 最后活跃/未读 | `session.db` 的 `SessionTable` | `last_timestamp`（Unix 秒）/`unread_count`/`is_hidden` |

### 关键点

- **group 表里 540 条 vs contact 表 541 条**：有 1 个群只在 contact 里、没有 chat_room 记录
  （通常是已退出但残留的群），脚本会保留它并把成员数记为 0。
- **整数 ID 是 `contact.id`**，不是 username。`chat_room.id` / `chatroom_member.room_id` /
  `chat_room_info_detail.room_id_` 三者**都指向 contact.id**，可直接 join。
- `session.db` 里 737 条会话 vs 423 个群有会话 → 有 118 个群**从未打开过或已静默**（`last_timestamp=0`）。
- 会话表**不含消息正文**（只有 `summary` 摘要字段，本脚本故意不取），所以此导出天然无聊天内容。
- 本脚本**不触碰任何 `Msg_*` 表**，是纯净的元数据导出。

---

## 群聊导出（一键脚本，2026-09-29 实测可用）

```bash
PY="C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
"$PY" "C:/Users/Lenovo/.workbuddy/skills/wechat-cli__skillhub/scripts/wx_export_group.py" \
      "<群ID>@chatroom" "<输出名>"
```

例：`"$PY" scripts/wx_export_group.py "22251947083@chatroom" "小鲜肉肉"`
→ 产出 `D:/WorkBuddy/2026-09-29-14-04-17/wx_export/小鲜肉肉_群聊记录.md`

脚本已内置：**全库遍历合并 + 去重 + 联系人名解析 + appmsg 卡片渲染**。

### 三步流程

1. **找群 ID**
   ```sql
   SELECT username, nick_name, remark FROM contact WHERE nick_name LIKE '%群名%';
   ```
2. **跑脚本**（上面一条命令）
3. **清理正文前缀**：群文本消息常常是 `**名字** (HH:MM)：wxid_xxx:  \n 正文` 两行结构，
   需把 `wxid_xxx:` 剥掉。脚本输出的第 2 行可能残留，用**跨行合并**处理：
   ```python
   # 关键：前缀和正文分在两行，要读下一行拼接
   if re.search(r"：\s*[A-Za-z0-9_\-]{5,}\s*:\s*$", ln):
       ln = re.sub(r"：\s*[A-Za-z0-9_\-]{5,}\s*:\s*$", "：" + lines[i+1].lstrip(), ln)
   ```
   只做**同行**替换会漏掉一半以上（实测 1108+532 处）。

### 成员名解析要点

- **显示名 = 你的备注**（`remark` > `nick_name` > `alias`），不是对方微信名。
- 有人 `user_name` 为空（非好友入群）→ 显示 `?<sender_id>`。若是 `[系统]` 类消息，实为微信本身。
- `chatroom_member` 表用**整数 rowid**（`room_id`/`member_id`），**不是** username，
  且不同账号库里这张表可能不存在 → 别指望它拿花名册。
- 想查某人真实微信名：用消息表里 `real_sender_id` → `Name2Id.user_name` → contact 表反查。

---

### 本机环境速查（2026-09-29 更新）
- Python（本机实际可用）：`C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe`
  - 已装 `zstandard`、`pycryptodome` 等依赖
- 微信版本：4.1.13.65，程序在 `D:/微信/Weixin/Weixin.exe`（6 个进程，主进程内存最大）
- 微信数据根：`D:/微信/聊天记录/xwechat_files/`（从 `%APPDATA%/Tencent/xwechat/config/*.ini` 读出）
- **本机账号**：`hejian0625_4fb9`（唯一账号），db_storage 在 `D:/微信/聊天记录/xwechat_files/hejian0625_4fb9/db_storage`（21 个 .db）
- 配置目录：`~/.wechat-cli/`（all_keys.json / config.json / all_keys_accountN.json）
- 微信需先启动并登录（`cd "D:/微信/Weixin" && cmd //c start "" Weixin.exe`），密钥提取必须微信在线
- 提权：读取自身用户启动的微信进程**不需要管理员权限**（实测非管理员 21/21 成功）
- 若换账号/微信重启后密钥变化，重跑 `extract_keys.py` 即可

### scripts/ 目录说明（2026-09-29 全部参数化）

| 脚本 | 用途 | 状态 |
|------|------|------|
| `extract_keys.py` | **推荐**。一步提取密钥（扫描+XOR 解码+校验+落盘） | ✅ 实测 21/21 |
| `wechat_key_xor.py` | 同上，早期独立版本 | ✅ 保留 |
| `dump_config_blobs.py` | 仅 dump blob 到磁盘 | ✅ 实测 25 blobs |
| `gen_keys.py` | 从已 dump 的 blob 离线解析密钥 | ✅ 实测 21/21 |
| `switch_account.py` | 多账号切换（自动发现账号，无需硬编码） | ✅ 实测可用 |
| `wcdb_key_tool_windows.py` | 解密库 + Config.Cipher 扫描（底层库） | 见下方说明 |
| `wx_export_favorites.py` | 收藏**全量**导出为 Markdown | ✅ 实测 613 条 |
| `wx_export_favorites_links.py` | 收藏**链接/文章专项**导出（type=5，含主题聚类） | ✅ 实测 374 条 |
| `wx_export_groups.py` | **全部群聊基本信息**导出（无聊天内容） | ✅ 实测 541 群 |

> `wcdb_key_tool_windows.py` 的 `extract` 子命令内部走的是 PBKDF2 路线，在 4.1.13 上
> 无法命中（已在文件头注明）。它的 `decrypt` 子命令正常可用，是解密数据库的标准入口。


## 参考文档

- [完整命令参考](references/commands.md)
- [消息分析工作流指南](references/analysis-guide.md)
- [常见问题排查](references/troubleshooting.md)
