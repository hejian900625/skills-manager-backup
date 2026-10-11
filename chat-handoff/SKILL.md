---
name: chat-handoff
description: "把当前对话压缩成一份交接文档，交给另一个 agent（或下一次会话）接手。文档保存到用户操作系统的临时目录，而非当前工作区；包含任务摘要、关键决策、剩余工作、已知坑、建议下一步调用的技能，并对敏感信息做脱敏。触发词：对话交接 / 交接 / handoff / 压缩上下文 / 换个会话继续。"
version: "1.0.1"
display_name: 对话交接
display_name_en: Chat Handoff
description_zh: "把当前对话压缩成一份交接文档，交给另一个 agent（或下一次会话）接手。包含任务摘要、关键决策、剩余工作、已知坑、建议下一步调用的技能，并对敏感信息做脱敏。"
description_en: "Compact the current conversation into a handoff document for another agent (or the next session) to pick up. Includes a task summary, key decisions, remaining work, known pitfalls, and suggested skills to call next, with sensitive information redacted."
license: "MIT; 由 田紫薇/穆天膳 收编、改名、中文双语适配 WorkBuddy 平台。"
author: 田紫薇/穆天膳
agent_created: true
---

# 对话交接 / Chat Handoff

写一份交接文档，总结当前对话，让一个全新的 agent 能接着把活干完。保存到用户操作系统的**临时目录**，而不是当前工作区。
Write a handoff document summarising the current conversation so a fresh agent can continue the work. Save to the temporary directory of the user's OS - not the current workspace.

文档里要包含「建议调用的技能」一节，指明下一任 agent 应该通过技能工具去调用哪些技能。
Include a "suggested skills" section in the document, naming which skills the next agent should call the Skill tool for.

不要把其他产物（规格、计划、ADR、issue、提交、diff）里已经有内容重复抄进来。用路径或链接引用它们即可。
Do not duplicate content already captured in other artifacts (specs, plans, ADRs, issues, commits, diffs). Reference them by path or URL instead.

对敏感信息做脱敏，例如 API key、密码、或个人可识别信息。
Redact any sensitive information, such as API keys, passwords, or personally identifiable information.

如果用户传了参数，把它们当作「下一次会话要聚焦做什么」的描述，据此调整文档。
If the user passed arguments, treat them as a description of what the next session will focus on and tailor the doc accordingly.

## 交接文档结构 / Handoff document structure

一份好的交接文档应包含：
A good handoff document should contain:

1. **任务摘要 / Task summary**——这次对话在干什么、目标是什么。
   What this conversation was about and what the goal was.
2. **关键决策 / Key decisions**——已经拍板的方向、理由、被否决的备选。
   Decisions already made, their rationale, and rejected alternatives.
3. **已完成的工作 / Work completed**——到目前做到哪了，产出了哪些文件/改动。
   What has been done so far, and which files/changes were produced.
4. **剩余工作 / Remaining work**——还差什么，按优先级列出。
   What is left, listed by priority.
5. **已知坑 / Known pitfalls**——踩过的雷、环境怪相、容易复发的问题。
   Traps hit, environmental quirks, issues likely to recur.
6. **建议调用的技能 / Suggested skills**——下一任 agent 该用哪些技能（列出技能名）。
   Which skills the next agent should invoke (list skill names).
7. **下一步 / Next step**——第一个该执行的动作。
   The first action to execute.

## 边界 / Boundaries

- 只总结，不替下一任 agent 做它该自己判断的决定。
  Summarize only; do not make decisions the next agent should judge for itself.
- 路径与链接优先于大段复制。
  Prefer paths and links over large copy-paste blocks.
- 脱敏是硬性要求，宁多勿少。
  Redaction is mandatory; when in doubt, redact.
- 文档落在临时目录，避免污染项目仓库。
  The doc lives in the temp directory to avoid polluting the project repo.
