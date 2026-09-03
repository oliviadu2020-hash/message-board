# AGENTS.md — 协同工作台规则

本仓库是一个多人协同工作台：所有协作记录都在本仓库中，以 git 历史为准。在本仓库内工作时，遵守以下规则。

## 铁则（务必遵守）

1. **对 `workspaces/<user>/inbox/` 的一切读写，必须通过 `cd workspaces && uv run scripts/sync.py` 完成，禁止直接创建、修改、删除其中的文件，也禁止对其中文件做直接的 git 操作。**
2. 写入收件箱的内容会永久留在 git 历史中（写信即公开发言），不得包含密钥、个人隐私等敏感信息。
3. 邮件不可删除/撤回；发错了的正确做法是再发一封更正（subject 可用「Re: 上一封作废」）。
4. 达成共识的产出（方案、决议、规范）必须沉淀到 `share/`，不要只留在邮件或对话里。
5. 重要工作在当前用户 `workspaces/<user>/log.md` 追加日志（按日期倒序，新内容加在标题之后）。
6. 当前用户身份记录在本机的 `workspaces/.current_user`，sync.py 会读取它；不要改动他人目录下的 `.sync_seen`。
7. `board/` 是 CI 自动重建的派生区（通知台账 + 任务看板），只读不改。
8. 任务状态变更一律用 `sync.py task` 完成（状态收敛为五态：未开始 / 进行中 / 阻塞 / 待确认 / 已完成）；只能动自己 `workspaces/<自己>/` 下的文件，他人目录一律只读。

## 新邮件提醒（UserPromptSubmit 时机）

每轮用户提交 prompt 时，UserPromptSubmit hook 自动执行 `sync.py check`，把未读邮件摘要作为附加上下文送进来。
若摘要非空：向用户复述要点并询问如何处理；需要回复时使用 `sync.py write` 回信（应答协同单时用 `--type 回执/退回 --ref <原单>`）。摘要与任务现状均为空则正常继续，不必提及。

## 常用命令（在 `<project>/workspaces` 下运行）

- 查未读 + 任务现状：`uv run scripts/sync.py check`（hook 已自动执行）
- 读全文：`uv run scripts/sync.py read [--filename <name>]`
- 写信：`uv run scripts/sync.py write --to <user>[,<user2>...] --subject "..." [--type 协同单|回执|退回 --ref <原单文件名>] (--content "..." | --file <path>)`
- 建任务：`uv run scripts/sync.py task create --name <任务名> [--from <协同单文件名>]`
- 更新任务：`uv run scripts/sync.py task update --name <任务名> [--status 状态] [--blocked 说明]`
- 列任务：`uv run scripts/sync.py task list`

## 新用户加入与初始化

当用户表达过初始化或加入意图（如「我要以 `<username>` 身份加入」「帮我初始化这个工作区」「开始使用这个工作台」），或在工作中发现 `workspaces/.current_user` 缺失、其对应用户目录不存在时：阅读并执行 `docs/quickstart.md` 中的步骤完成初始化，不要凭记忆自行初始化。

## 完整协议

工作台的完整设计协议（目录结构、命令行为、设计规则）见 `docs/prd.md`。本文件与 PRD 冲突时，以 PRD 为准。
