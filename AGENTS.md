# AGENTS.md — 协同工作台规则

本仓库是一个多人协同工作台：所有协作记录都在本仓库中，以 git 历史为准。在本仓库内工作时，遵守以下规则。

## 铁则（务必遵守）

1. **对 `workspaces/<user>/inbox/` 的一切读写，必须通过 `cd workspaces && uv run scripts/sync.py` 完成，禁止直接创建、修改、删除其中的文件，也禁止对其中文件做直接的 git 操作。**
2. 写入收件箱的内容会永久留在 git 历史中（写信即公开发言），不得包含密钥、个人隐私等敏感信息。
3. 邮件不可删除/撤回；发错了的正确做法是再发一封更正（subject 可用「Re: 上一封作废」）。
4. 达成共识的产出（方案、决议、规范）必须沉淀到 `share/`，不要只留在邮件或对话里。
5. 重要工作在当前用户 `workspaces/<user>/log.md` 追加日志（按日期倒序，新内容加在标题之后）。
6. 当前用户身份记录在本机的 `workspaces/.current_user`，sync.py 会读取它；不要改动他人目录下的 `.sync_seen`。

## 会话开始时

SessionStart hook 会自动执行 `sync.py check`，呈递当前用户的未读邮件。
若有新邮件：向用户复述要点并询问如何处理；需要回复时使用 `sync.py write` 回信。

## 常用命令（在 `<project>/workspaces` 下运行）

- 查未读：`uv run scripts/sync.py check`（hook 已自动执行）
- 读全文：`uv run scripts/sync.py read [--filename <name>]`
- 写信：`uv run scripts/sync.py write --to <user>[,<user2>...] --subject "..." (--content "..." | --file <path>)`

## 新用户加入与初始化

当用户表达过初始化或加入意图（如「我要以 `<username>` 身份加入」「帮我初始化这个工作区」「开始使用这个工作台」），或在工作中发现 `workspaces/.current_user` 缺失、其对应用户目录不存在时：阅读并执行 `docs/quickstart.md` 中的步骤完成初始化，不要凭记忆自行初始化。

## Changelog

**ALWAYS REMEMBER: 记录每一次变更到顶层 `CHANGELOG.md`。** 不管是代码、配置、资源还是文档变更，都要在同一个 change set 中新增条目：

- 最新条目加在 `CHANGELOG.md` 顶部
- 用真实日期
- 描述具体的用户可感知或工程上的变化，避免写「优化」这类空泛条目
- 纯文档、维护类变更也必须记录

## 完整协议

工作台的完整设计协议（目录结构、命令行为、设计规则）见 `docs/prd.md`。本文件与 PRD 冲突时，以 PRD 为准。
