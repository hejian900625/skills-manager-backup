# QQ NT 数据库格式与解密技术参考

## 1. 文件位置（Windows）

QQ NT 数据根目录（每个登录账号一个子目录，以 QQ 号命名）:

    C:/Users/<系统用户>/Documents/Tencent Files/<QQ号>/nt_qq/nt_db/

该目录下是若干 `*.db`（如 `nt_msg.db` 主消息库、`group_info.db` 群信息、
`profile_info.db` 好友资料等）。本机示例账号 `181013051`。

## 2. 文件结构（每个 db）

| 偏移 | 内容 |
|------|------|
| 0 – 1023 | 自定义 1024 字节头（魔数 `SQLite header 3` + `QQ_NT DB` + protobuf 头，含 64 字节 salt/128 hex、`version 1.1.0.1`、`HMAC_SHA1`） |
| 1024 – EOF | SQLCipher 加密区 |

`nt_msg.db` 约 22 MB（5632 页 × 4096）。解密前必须先用脚本剥离前 1024 字节。

## 3. SQLCipher 解密参数（官方 `1.decrypt.py` 实测，务必按顺序）

    PRAGMA cipher_page_size = 4096;        -- 必须在 key 之前
    PRAGMA key = '<16字节ASCII key>';
    PRAGMA kdf_iter = 4000;
    PRAGMA cipher_hmac_algorithm = HMAC_SHA1;
    PRAGMA cipher_kdf_algorithm = PBKDF2_HMAC_SHA512;   -- 派生 32 字节密钥

> 注意：`sqlcipher3` 某些 wheel 会忽略 `cipher_hmac_algorithm`，实际走 SHA1/SHA512
> 取决于编译；但 QQ 官方客户端写入时用的就是上面这组，所以用该库按序执行即可还原。

## 4. 解密 key 的来源

key 是一个 **16 字节 ASCII 字符串**，明文驻留在 `QQ.exe` 进程内存中
（由 `nt_sqlite3_key_v2` 调用时写入，校验 `keyString.Length==16` 且每个字符 32–126）。

两种取法:
- **内存扫描（本 skill 主路径，已验证）**: 用 `scan_keys.py` 枚举进程可写提交内存，
  用边界精确正则 `(?<![ -~])[ -~]{16}(?![ -~])` 提取全部 16 字节可打印串，再用
  `brute_key.py` 以 `sqlcipher3` 并行逐一验证，首个能 `SELECT count(*) FROM sqlite_master`
  成功的即真 key。
- **官方调试器提 key（备选）**: `windows_ntqq_get_key.ps1`（QQBackup/qq-win-db-key 仓库）
  通过 Windows 调试 API 附加 QQ，在 `nt_sqlite3_key_v2` 调用点读 R8 寄存器指向的 16 字节
  key。需要 PowerShell 7+ 与调试权限，环境受限时不如内存扫描稳。

## 5. 消息表列映射（QQ NT 新版，列名是数字 ID，**版本敏感**）

主消息库 `nt_msg_plain.db` 含表: `c2c_msg_table`(私聊)、`group_msg_table`(群聊)、
`c2c_msg_flow_table`、`group_msg_flow_table` 等。

| 列 ID | 含义 |
|-------|------|
| 40001 | 消息 id |
| 40010 | 会话类型: 1=私聊(c2c), 2=群聊(group) |
| 40011 | 消息类型 |
| 40020 | 发送者 uid |
| 40090 | 发送者昵称 |
| 40021 / 40027 | 对端 / 群 uin |
| 40050 | 发送时间 (Unix 秒) —— 真实逐条时间；`40058` 多为 -1/常量，勿用 |
| 40800 | 内容 BLOB（protobuf，内含 UTF-8 文本片段） |

> `SELECT 40001` 会被 SQLite 当成整数字面量，必须用引号: `SELECT "40001"`。

## 6. 内容 BLOB（40800）解析

`40800` 是 protobuf 二进制，文本片段以 UTF-8 字符串字段嵌在其中（可能多层嵌套、
夹杂 emoji 与 CJK）。`export_chats.py` 用**通用 protobuf walker**（递归遍历 varint tag，
对 `wire type 2` 的字节串做 UTF-8 合法性 + CJK/标点判定）抽取全部文本片段，
去重后用空格拼接为消息正文。非文本消息（图片/文件/表情）无可读文本，标为
`[非文本消息]`（未做媒体二进制还原）。

## 7. 群名解析

`group_info_plain.db` → 表 `group_list`，用 `60001`/`60221` 作 uin key、`60007` 作群名
（`SELECT "60001","60221","60007" FROM group_list`）。已退群或不在 `group_list` 中的群
以原始 uin 显示。

## 8. 已知坑与规避

- **WITHOUT ROWID 表陷阱**: 部分表无 rowid，早期用 `SELECT rowid` 分页会抛异常进入
  死循环（CPU 空转、进程看似卡死）。解法是直接用 `SELECT *` + 游标 `fetchmany` 流式导出，
  不入 rowid 依赖。
- **FTS/pinyin 自定义分词器**: `pinyin_letter` 等自定义 tokenizer 的表建表语句在裸
  sqlite3 中执行会失败，属预期，跳过即可，不影响聊天记录。
- **多进程写同一 key 文件**: 并行暴力时多个 worker 可能同时写 `qq_key.txt`，命中后
  立即 cancel 其余 future 即可避免竞争。
- **不要重复运行 decrypt_all**: 脚本已做增量判断（clear/plain 大小匹配则跳过），但
  重复跑会占用额外 IO；需要重跑建议先清 `qq_out`。
- **环境依赖**: 解密必须 `sqlcipher3`（本机托管 Python 3.13 cp313 win_amd64 wheel 已验证）。
  裸跑前确认 `python -c "import sqlcipher3"` 通过。
