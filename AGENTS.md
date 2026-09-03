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

## 任务与看板怎么用（task / board）

**任务从哪里来？** 收到协同单（type: 协同单）后，若接下来要做，就建一个任务包挂住它；一张协同单对应一个任务包。建任务时用 `--from` 记下上游协同单文件名（引擎会自动补 `inbox/` 前缀写进 task.yaml 的 `from` 字段），这样"哪张单派出了哪个活"可追溯。不想接的单**不要建任务**，直接 `write --type 退回 --ref <原单>` 退回。

**任务状态怎么流转？** 任务状态只有五态，一律用 `sync.py task update` 改，禁止手改 task.yaml：

| 你要做什么 | 命令 |
|---|---|
| 接下来接这单、建任务包 | `task create --name <任务名> [--from <协同单文件名>]`（初始态=未开始） |
| 开始动手 | `task update --name <任务名> --status 进行中` |
| 卡住了（等别人/缺东西） | `task update --name <任务名> --status 阻塞 --blocked "等 <谁> <什么>"` |
| 干完、交付给派单人 | `task update --name <任务名> --status 待确认`，并发回执 `write --type 回执 --ref <原单>` |
| 对方确认收下 | `task update --name <任务名> --status 已完成`（闭环） |

注意：`task update` 至少要给 `--status` 或 `--blocked` 之一；状态不是「阻塞」时 blocked_by 会被复位成「无」。update 之后 `updated` 自动落当天日期。列自己全部任务：`task list`。

**board/ 是什么、怎么看？** `board/` 是 CI（board.yml）在每次 push 后自动重建的**全局读视图**，给人和 Agent 看全组状态用的，本地永远只读、不手改（改了会被下次 CI 覆盖，且属 lint 违规）：

- `board/task-board.md`：全员任务看板，按五态分列（每行含任务名、owner、上游 from、blocked_by）；
- `board/ledger/<user>.md`：某人收件流水台账（时间/发件人/类型/标题/ref），按时间倒序；
- 网页版（github.io）与这两个 Markdown 同源，看审计/演示用它。

**什么时候读什么：** 汇报"我手头有什么"→ `task list`；汇报"全局/某人状态、谁阻塞最多"→ 读 `board/`（先 `git pull` 拿最新）；hook 已自动把"新信 + 任务现状"送进来。本地想即时预览全局视图而不等 CI：`uv run scripts/derive.py render --workspaces $PWD --board-dir /tmp/board --data-json /tmp/data.json`（产物在 /tmp，不进 git）。

## 新用户加入与初始化

当用户表达过初始化或加入意图（如「我要以 `<username>` 身份加入」「帮我初始化这个工作区」「开始使用这个工作台」），或在工作中发现 `workspaces/.current_user` 缺失、其对应用户目录不存在时：阅读并执行 `docs/quickstart.md` 中的步骤完成初始化，不要凭记忆自行初始化。

## 完整协议

工作台的完整设计协议（目录结构、命令行为、设计规则）见 `docs/prd.md`。本文件与 PRD 冲突时，以 PRD 为准。
