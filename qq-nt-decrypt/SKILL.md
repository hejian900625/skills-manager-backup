---
name: qq-nt-decrypt
description: "This skill decrypts and exports local QQ NT (QQ Windows 9.x / NT architecture) data from this machine: chat history, group basic info, and friend list. It extracts the 16-byte SQLCipher key from the running QQ.exe process memory, decrypts the nt_db SQLite databases, and exports to CSV plus interactive HTML viewers. Trigger phrases: QQ 聊天记录, 解密 QQ, 导出 QQ NT, QQ NT key, QQ 好友, 好友列表, 导出 QQ 好友, 获取好友列表, or any request to read or parse local QQ data files. Not for WeChat (use wechat-cli) and not for QQ cloud or remote data."
agent_created: true
---

# QQ NT 聊天记录解密与导出

## Overview

QQ NT（Windows 9.x 之后的新架构）把聊天记录存为本机 SQLite 数据库，但用 SQLCipher
加密、并带 1024 字节自定义头，普通工具打不开。本 skill 提供一条已端到端验证的流水线：

1. 从运行中的 `QQ.exe` 进程内存扫描出 16 字节 ASCII 解密 key 候选；
2. 用官方同款 `sqlcipher3` 参数并行暴力验证出真 key；
3. 剥离头部后解密 `nt_db` 下全部数据库；
4. 解析 protobuf 消息内容 + 群名映射，导出 CSV 与自包含 HTML 查看器。

适用：**本机已登录的 QQ NT 账号**的本地数据。不适用：微信（用 `wechat-cli`）、
QQ 云端/远程数据、未登录或非 NT 架构的旧版 QQ。

## 依赖与前提

- 本机已登录 QQ NT（进程 `QQ.exe` 在线，否则内存里没有 key）。
- 解密需要 `sqlcipher3`，本机托管 Python 环境（cp313 win_amd64 wheel）已验证可用。
  运行前确认：`python -c "import sqlcipher3"` 不报错。缺失时安装该预编译 wheel。
- 仅在 Windows 上运行（脚本调用 Windows API 与 `tasklist`）。

## 快速开始（一键流水线）

进入本 skill 的 `scripts/` 目录，用托管 Python 直接跑编排器：

```bash
python run_all.py                 # 默认输出到 ./qq_out
python run_all.py --outdir D:/qq_export
python run_all.py --qqdir "C:/Users/x/Documents/Tencent Files/123"   # 跳过自动探测
```

`run_all.py` 会依次完成：探测 PID 与 `nt_db` 目录 → 扫描内存候选 → 暴力 key →
解密全部库 → 导出聊天记录，产物落在 `<outdir>/qq_messages.csv` 与 `<outdir>/qq_chat.html`。

## 分步用法（脚本可单独调用）

若需逐步控制或复用中间产物，按以下顺序调用 `scripts/` 内脚本：

### 1. 扫描候选 key — `scan_keys.py`
```bash
python scan_keys.py --out qq_key_candidates.txt        # 自动探测 QQ.exe PID
python scan_keys.py --pid 18768 --out candidates.txt   # 指定 PID
```
枚举进程可写提交内存，用边界精确正则提取所有 16 字节可打印 ASCII 串作为候选
（实测约 27 万候选）。

### 2. 暴力验证 key — `brute_key.py`
```bash
python brute_key.py --src nt_msg.db --cand qq_key_candidates.txt --key qq_key.txt
```
先剥离 `nt_msg.db` 前 1024 字节头得到 `*_clear.db`，再用 `sqlcipher3` 按固定 PRAGMA
序列（cipher_page_size=4096 → key → kdf_iter=4000 → HMAC_SHA1 → PBKDF2_HMAC_SHA512）
并行验证每个候选，首个能读 `sqlite_master` 的即真 key，写入 `--key` 文件。

### 3. 解密全部库 — `decrypt_all.py`
```bash
python decrypt_all.py --srcdir "<nt_db 目录>" --outdir qq_out --key qq_key.txt
```
对每个 `*.db` 剥离 1024 头 → 用 key 打开加密区 → 逐表游标导出为 `*_plain.db`（裸
sqlite3，含全部表与数据）。遇到损坏行降级单行插入跳过，FTS/pinyin 自定义分词器表
失败不影响其它表。

### 4. 导出聊天记录 — `export_chats.py`
```bash
python export_chats.py --outdir qq_out
```
读取 `*_plain.db`，用通用 protobuf walker 抽取 `40800` 列（内容 BLOB）中的 UTF-8 文本，
从 `group_info_plain.db` 解析群名，输出：
- `qq_messages.csv`：时间/类型/对端ID/对端名称/发送者UID/发送者昵称/内容类型/内容
- `qq_chat.html`：自包含交互查看器（左侧会话列表+搜索，右侧时间线）

### 5. 导出群聊基本信息（不含聊天记录）— `export_groups.py`
```bash
python export_groups.py --outdir qq_out
```
读取已解密的 `group_info_plain.db`，关联 `group_list` 与 `group_detail_info_ver1`（按群号 60001 连接），输出：
- `qq_groups.csv`：群号 / 群名称 / 群标识码(长号) / 成员数 / 成员上限 / 群主UID / 加群验证问题 / 等级码 / 等级分 / 群分类码 / 备注
- `qq_groups.html`：自包含可搜索表格（按成员数降序）

> 说明：群主以 QQ NT 的 `u_xxx` uid 形式给出（非明文昵称）；`成员数` 为群资料声明的成员总数（本地 `group_member3` 仅缓存部分成员，非全量名单）。
> 群主昵称尽力解析：优先 `profile_info_plain.db.profile_info_v6`（通用档案缓存，覆盖被客户端查询过的 uid），回退 `group_member3` 缓存成员名单；二者都缺的群主只剩 `u_xxx` uid（昵称需联网向 QQ 服务器查，离线拿不到）。实测 123 群中约 52 个可解析昵称。

### 6. 导出好友列表（基本信息，不含聊天记录）— `export_buddies.py`
```bash
python export_buddies.py --outdir qq_out
```
读取已解密的 `profile_info_plain.db`：`buddy_list` 提供好友 uid 列表 + 分组ID，
`profile_info_v6`（通用档案缓存，约 2.3 万条）反查昵称/个性签名/备注，输出：
- `qq_buddies.csv`：好友UID / 昵称 / 备注 / 个性签名 / 分组ID
- `qq_buddies.html`：自包含可搜索表格（按昵称排序）

> 说明：QQ NT 用 `u_xxx` uid 代替数字 QQ 号，本机档案缓存**不含数字 QQ 短号**，故无法导出短号。好友昵称覆盖率通常很高（实测 478 位好友中约 476 位有昵称）。备注若本地未存则留空。

## 关键技术细节

完整格式、列映射、参数、坑点见 `references/qq_nt_format.md`（含 1024 头结构、
SQLCipher PRAGMA 顺序、消息列 ID 含义、protobuf 解析思路、已知陷阱与规避）。

## 产物说明

- 非文本消息（图片/文件/表情）在内容列标为 `[非文本消息]`，未做媒体还原。
- 列 ID（`40001`/`40050`/`40800` 等）随 QQ 版本变化，若某次解析为空，先按
  `references/qq_nt_format.md` §5 重新 inspect 表结构。
