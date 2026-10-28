# wechat-group-digest · 群刊编辑部

把微信群聊记录做成**「AI 提炼 + 统计瘦身」的单文件网页札记**：按月切片 → AI 通读 → 编辑部稿 → 渲染成一份可离线双击打开的 HTML 群刊。

> **铁律：页面必须经 AI 提炼，不能纯自动生成。** 统计脚本只配做数字，配不出"编辑部"——每一条知识、判词、语录都由 AI 通读原文后写出，并带出处日期可回查。

## 它产出什么

一份单文件 HTML（无 CDN、离线可用、双击即看），典型结构：

- **概览**：群龄 / 消息数 / 发言人数 + 逐日消息曲线
- **话题地图**：d3-force 力导向图，节点=可复用概念，**可拖拽、联动邻居**（引擎内嵌 vendor，17.5KB）
- **群像**：发言榜（自动剔除客服/机器人）+ Top 人物判词卡
- **领域手册**：按问题域组织的知识章节——每条写成"结论/做法 + 要点 + 两级标签 + 置信度"，读者能照着做，不是编年史
- **时间胶囊 / 语录 / 尾声**：叙事与温度

## 环境要求

- Python 3.10+（**零第三方依赖**，图谱引擎已内嵌 vendor 文件）
- 前置数据：`wechat_stats.db`（由姊妹项目 wechat-group-export 的 `--sqlite` 产出）

## 快速开始

### 方式 A：交给 AI（推荐）

本技能的服务对象就是 AI：切片是给 AI 读的原文，`digest.json` 是 AI 写的编辑部稿。把本仓库的 `SKILL.md` 交给支持技能机制的 AI（WorkBuddy / Claude 等），说一句"给 XX 群做份群刊"，AI 会完成：切片 → 通读 → 写稿 → 渲染 → 呈现，全程无需你干预。

### 方式 B：命令行（配合 AI 通读）

```bash
# DB 是你的 wechat_stats.db（wechat-group-export 产出）
DB="D:/微信群导出/wechat_stats.db"

# ① 切片：全量聊天文本按月落盘（AI 通读的输入）
python scripts/export_digest_src.py --group 群名片段 --db "$DB"

# ② AI 逐月通读 digest_src/<群名>/*.txt
# ③ AI 判群型、定领域假设，写编辑部稿 insights/<群>_digest.json
#    （schema 见 SKILL.md L2；铁律：缺此稿渲染会拒跑）

# ④ 渲染成单文件 HTML（默认输出到 <db目录>/outputs/rendered/<群名>_群刊.html）
python scripts/render_group_page.py --group 群名片段 --db "$DB"
```

脚本遵循**程序与数据分离**：不写死数据库路径。切片默认落 `<db目录>/.workbuddy/digest_src/`，成品 HTML 默认落 **`<db目录>/outputs/rendered/`**（与导出的聊天记录分目录存放）。

## 目录结构

```
wechat-group-digest/
├── SKILL.md                     # 技能说明书（L1 方法论 / L2 内容结构 / L3 Web 呈现）
├── scripts/
│   ├── export_digest_src.py     # ① 切片：库 → 按月 txt
│   ├── render_group_page.py     # ④ 渲染：digest.json → 单文件 HTML（CSS/JS 单真源）
│   ├── make_persona_src.py      # 人物判词原料：Top10 每人全量文本（供子 Agent 精读）
│   ├── cnb_push.sh              # 推本仓到 CNB（自动注入正确 token + 绕开失效代理）
│   └── vendor/d3-force.min.js   # d3-force v3 UMD（ISC），仅图谱版块按需内联
└── LICENSE
```

## 适配性：一个技能服务各种群

- **不写死领域清单**：先按群型识别（技术研讨/资源分享/行业协作/兴趣交流/综合闲聊），再由 AI 从通读中提炼这个群**真实**的 3~5 个问题域，回挖原文验证，挖不出料就砍
- **版块全可缺省**：闲聊群可以没有图谱、没有速查表——digest.json 里有什么字段就渲染什么
- **大群自动降级**：切片总量 >100KB 时走分片 map-reduce 通读（子 Agent 并行精读 + 主编汇稿），127 群 2.1 万条实测可跑

## 隐私

页面为单文件、无外链、数据不离开本地；页面底部署名数据源与提炼方式，引语均出自原文。

## 姊妹项目

[**wechat-group-export**](https://cnb.cool/fzz198479/wechat-group-export) · 微信群聊导出——解密微信本地库并产出 `wechat_stats.db`，是本项目的数据源。export 采矿，本技能办刊。

## License

MIT。内嵌 `scripts/vendor/d3-force.min.js` 为 d3-force / d3-dispatch / d3-quadtree / d3-timer（ISC，Copyright 2010-2021 Mike Bostock），版权归原作者，详见 `LICENSE` 的 Third-party notices。
