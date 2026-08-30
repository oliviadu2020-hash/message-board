# Message Board PRD

基于Agent的多人协同工作台搭建

---

## 背景

### 从一个常见的场景说起

想象一个典型场景：多位成员协作开发一个功能，需求讨论发生在企业即时通讯群里。你一言我一语，中途穿插着其他话题和表情包，三天后终于达成了一致。接下来问题来了——

- **讨论过程找不回来了**。当时为什么选择方案 A 而不是方案 B？谁反对过、反对的理由是什么？翻聊天记录要翻几百条，大部分是无关内容。
- **结论靠人工搬运**。讨论出的共识，要靠人手动整理成文档、更新到工程里。忘了搬，或者搬的时候漏了一句，工程记录就和真实决策脱节了。
- **后来的协作者（包括 AI）看不到上下文**。新加入的人只能看到"最终方案长什么样"，看不到"为什么长这样"，很容易把已经否决过的弯路再走一遍。

这不是某个团队的问题，而是多人协作的通病：**讨论发生在一个地方（聊天工具），工程沉淀在另一个地方（代码仓库），中间靠人肉同步。**

### 为什么现在值得重新解这个问题

AI 助手（Agent）的普及带来了一个新变化：团队里多了一类"数字协作者"。Agent，指能自己动手读写文件、执行命令的 AI 助手，比如 Claude Code、Codex。它们和人一起推进工程，但它们看不到你的微信群——**它们能看到的全部世界，就是这个工程目录。**

行业里把这种"围绕 Agent 来设计工程协作方式"的实践称为 Harness Engineering（可理解为"给 Agent 驾驭工程的缰绳"），它的一条核心要求是：**工程本身要成为一套完整的记录系统**——需求怎么来的、讨论怎么推进的、共识是什么，都要沉淀在工程里，这样 Agent（以及新加入的人）才能完整理解上下文，给出靠谱的协助。

于是我们要解决的问题变成了：**如何让多人协作推进需求的全过程，自然地沉淀到工程里，而不是散落在聊天记录中？**

这个仓库就是我们的答案：一个基于 Agent + Git 的协同工作台 demo。我们希望做到：协作的每一步（发消息、讨论、达成共识）都以文件形式留在工程中，人和 Agent 随时能回看完整的来龙去脉。

---

## 实现思路

用一个生活化的类比来说：我们给每位协作者在工程里设了一个**邮箱**，把"发通知"变成"投信"，把"开始工作"变成"先查信箱"。

- **工程即邮局**：整个工程由 git（一个版本管理工具，可以理解为"带完整历史记录和云端同步功能的文件夹"）承载。每位协作者都在本地持有一份完整的工程副本，改完后与云端同步。
- **发消息 = 送信**：用户 A 想通知用户 B，就让自己的 Agent 写一封信（本质是一个 Markdown 纯文本文件），投进用户 B 在工程里的"收件箱"，然后同步到云端。
- **收消息 = 查信箱**：用户 B 每次向自己的 Agent 发起新一轮对话时，B 的 Agent 会通过 Hook（一种"每次用户提交 prompt 时自动执行指定动作"的机制）自动检查 B 的收件箱。如果有未读信件，Hook 会把摘要拼成一条"叮咚"提醒，作为上下文一并交给 Agent，Agent 据此向 B 呈递。B 读完即可处理，整个来龙去脉都已躺在工程里。

这样做，消息本身就是工程文件，天然被 git 记录、同步、追溯——讨论过程即工程历史，不再需要人工搬运。

**多人同时写信会不会冲突？**——不会。git 的冲突本质是"两个人同时改了同一文件的同一行"。本设计里每封信都是一个**独立的新文件**，文件名带时间戳和发件人，天然不重名；无论多少人同时写信，都只是"仓库里多了几个新文件"，不存在内容冲突。极端情况下，最后一步 `git push` 可能因为"本地落后于云端一个新提交"被拒——sync.py 会自动重新 pull 再 push，最多重试 3 次，超出则报错交还给 Agent（比如稍后重发）。写信的人全程不需要懂 git。

## 目录结构

这个的实现与工程目录密切相关，我们的初步想法如下：

```
<project_name>/             # 工程根目录
├── .claude/settings.json   # Claude UserPromptSubmit hook 配置
├── .codex/hooks.json       # Codex UserPromptSubmit hook 配置
├── share                   # 共享文件（达成共识的文件存放位置）
|   └──（自由文件）
├── workspaces
│   ├── .current_user       # 保存了本地的用户是谁
│   ├── <user1>
│   |   ├── inbox/          # <user1> 的收件箱
│   |   ├── .sync_seen      # <user1> 的已读消息记录
|   |   ├── workspace       # <user1> 的个人工作区（草稿区）
|   |   └── log.md          # <user1> 的个人工作日志
│   ├── <user2>
│   |   ├── inbox/          # <user2> 的收件箱
│   |   ├── .sync_seen      # <user2> 的已读消息记录
|   |   ├── workspace       # <user2> 的个人工作区（草稿区）
|   |   └── log.md          # <user2> 的个人工作日志
│   ├── scripts/sync.py     # workspaces的CLI 引擎（支持邮件的读、写、检查）
│   ├── hooks/on_prompt.sh  # UserPromptSubmit hook 的统一入口脚本（自行定位仓库根，不依赖 hook 执行时的 cwd）
│   ├── pyproject.toml      # uv 项目定义
│   ├── uv.lock             # 依赖锁
│   └── .python-version     # python 3.12
├── docs/prd.md             # 本设计协议（随模版分发，见附录）
├── docs/quickstart.md      # 新协作者的上手步骤（由 Agent 阅读并执行）
├── .gitignore              # 忽略清单（内容见「设计规则」中的约定）
├── AGENTS.md               # Agent 入口指引（含写入铁则），需要写清楚整个工作区的运转机制，并引用 docs/quickstart.md
├── CLAUDE.md → AGENTS.md   # 软链接（Claude Code）
└── README.md               # 整个工程的README.md文件
```

---

## 设计规则

- **workspaces/scripts/sync.py**：支持对消息的读、写、检查。以下命令示例的运行方式统一为：先 `cd <project>/workspaces`，再 `uv run scripts/sync.py ...`（`uv run` 从当前目录向上发现 `pyproject.toml`，使用 `workspaces/.venv` 环境）
  - 约定：`{.current_user}` 表示**读取 `workspaces/.current_user` 文件内容得到的用户名**（去掉首尾空白），sync.py 启动时读取一次；若文件不存在或为空，应报错并提示先写入当前用户名
  - 读：`uv run scripts/sync.py read [--filename {filename}]`：
    1. 执行`git pull`
    2. 如果没有指定{filename}，则读取`workspaces/{.current_user}/inbox`中所有未读消息（`workspaces/{.current_user}/.sync_seen`中记录了哪些消息已读），并且将这封消息记录到`workspaces/{.current_user}/.sync_seen`中标记为已读；如果指定了{filename}，则直接读取workspaces/{.current_user}/inbox/{filename}这个消息
  - 写 `uv run scripts/sync.py write --to {userx},{usery} [--content {md_content} | --file {filename}] --subject {subject}`：
    - `--content` 与 `--file` 二选一：`--content` 直接传邮件正文文本；`--file` 从文件读取正文。**`--file` 的路径支持绝对路径与相对路径**（相对路径按命令执行时的当前工作目录解析，与 `cat`/`cp` 等 Unix 命令一致）——邮件正文文件可以在仓库之外（例如 Agent 在 `/tmp` 起草的中间稿），只有最终生成的收件箱文件才进入版本库
    1. 执行`git pull`
    2. 基于{subject}中的内容和{md_content}(或者{filename}中读取出来的内容)构建要发送的markdown文件：格式为：
    ```markdown
    ---
    from: {.current_user}
    to:
      - {userx}
      - {usery}
    date: YYYY-MM-DD HH:mm:ss Z   # Z 为 UTC 偏移，如 +0800（对应 Python strftime: %Y-%m-%d %H:%M:%S %z）
    subject: {subject}
    ---
    {md_content(或者是{filename}中读取出来的内容)}
    ```
    3. 对 `--to` 中的每个收件人，分别将该 markdown 文件写入到 `workspaces/{每个收件人}/inbox/YYYY-MM-DD-HH-mm-ss-Z-{.current_user}.md` 中（内容相同，文件名相同；Z 为 UTC 偏移如 `+0800`，在文件名中合法）
    4. 执行`git add -> git commit -m "docs: {.current_user} sends a message to {userx},{usery}" -> git push`（commit message 中列出所有收件人）
    > 极端情况：若在步骤 1（`git pull`）之后、步骤 4（`git push`）之前，其他用户推了新提交导致 push 被拒，必须重新 `git pull` 合并后再 push；**最多自动重试 3 次**，超出则报错退出，交还给调用方（Agent）决定稍后重发。
  - 检查 `uv run scripts/sync.py check [--fmt json | markdown(默认以markdown格式输出)]`：
    1. 执行git pull
    2. 检查`workspaces/{.current_user}/inbox`中所有未读消息，然后按照格式进行输出
      - 如果--fmt指定为了json，则输出格式为:
      ```json
      [
        {
          "from": "xxx",
          "to": ["userx", "usery"],
          "date": "YYYY-MM-DD HH:mm:ss Z",
          "subject": "这里是一段简介"
        }
      ]
      ```
      - 如果指定格式为markdown，则输出格式为：
      ```markdown
      |发件人|收件人|日期|标题|
      |-----|-----|---|----|
      |from | to |date|subject|
      ```


- **收件箱（`workspaces/<user>/inbox/`）**
  - **禁止**通过直接使用git操作该工作区，**必须**通过sync.py来操作
  - **消息不可删除/撤回**：邮件文件一旦推送即永久保留（git 历史即完整通信史，这是"工程即记录系统"的核心）。发错了的正确处置是**再发一封信**（如 subject 为「Re: 上一封作废」）更正
  - 推论：**写信即公开发言**——写进收件箱的内容会永久留在 git 历史中，所有协作者可见，注意不要写入密钥、个人隐私等敏感信息（sync.py 不提供也不应提供敏感内容的擦除能力）

- **已读消息文件名列表（workspaces/<user>/.sync_seen）**
  - 记录该用户 inbox 中已读消息文件名列表
  - 仅本人写入 sync.py，禁止其他操作
  - 不入版本库（加入到 .gitignore 中）：已读状态是设备本地状态，同一用户多台机器各自维护；若未来需要"已读回执"，应做成显式功能而非同步此文件

- **个人工作区（workspaces/<user>/workspace）**
  - 某个用户的个人工作区

- **工作日志（workspaces/<user>/log.md）**
  - 某个用户的工作日志（由用户本人或其 Agent 维护，sync.py 不参与）
  - 建议格式（非强制）：Markdown，**按日期倒序**，新内容追加在标题之后、旧内容之前（两人同时写日志时各加各的日期段，可最大幅度降低 git 合并冲突概率）。示例：
    ```markdown
    # alice 的工作日志

    ## 2026-08-30
    - 与 bob 讨论了登录方案选型（详见 inbox/2026-08-30-10-00-00-+0800-bob.md）
    - 共识已沉淀至 share/auth-design.md

    ## 2026-08-29
    - ...
    ```

- **当前用户（workspaces/.current_user）**
  - 记录当前用户是谁
  - 不入版本库(加入到.gitignore中)

- **共享工作区（`share/`）**
  - 所有协作方自由读写，所有沉淀下来的文档需要写入这个

- **开箱上手（`docs/quickstart.md`）**
  - 新协作者的上手流程**由 Agent 执行，而不是由人手动敲命令**：人只需克隆仓库并告诉 Agent「我要以 `<username>` 身份加入」，Agent 阅读 `docs/quickstart.md` 后完成全部初始化（写入 `workspaces/.current_user`、创建 `workspaces/<username>/` 及 inbox/workspace/log.md、首次 commit + push、发信自测验证链路）
  - `AGENTS.md` 必须引用 `docs/quickstart.md`，使 Agent 发现新用户（`workspaces/.current_user` 不存在，或对应用户目录不存在）时知道去哪里读上手步骤
  - 用户名约定：全小写英文或拼音（避免中文名在文件名、git、跨平台上的兼容问题）

- **仓库忽略文件（`.gitignore`）**
  - 必须包含以下内容（本地状态、运行环境、系统杂物均不进版本库）：
    ```gitignore
    # Python / uv 环境
    workspaces/.venv/
    __pycache__/

    # 设备本地状态（每台机器各自维护，见设计规则）
    workspaces/.current_user
    workspaces/*/.sync_seen

    # 系统杂物
    .DS_Store
    ```

---

## Hook 配置

Claude 与 Codex 的 UserPromptSubmit hook 都指向同一个入口脚本 `workspaces/hooks/on_prompt.sh`（已提交进仓库），不在 hook 配置里写绝对路径，因此每个协作者 clone 到任意路径都无需修改配置。

每次用户提交 prompt，hook 都会自动跑一次 `sync.py check`。若收件箱为空、无未读邮件，入口脚本静默退出（exit 0、零输出），不打断用户与 Agent 的对话；若有未读邮件，脚本以「叮咚」形式把摘要包装后输出，Claude Code / Codex 会把这段输出作为附加上下文注入当轮对话，使 Agent 知道"有新邮件到了"。

### `.claude/settings.json`

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd \"$CLAUDE_PROJECT_DIR\" && bash workspaces/hooks/on_prompt.sh"
          }
        ]
      }
    ]
  }
}
```

### `.codex/hooks.json`

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "bash workspaces/hooks/on_prompt.sh"
          }
        ]
      }
    ]
  }
}
```

- Codex 的 hook 以仓库根为 cwd 执行，command 直接使用相对路径入口
- 入口脚本内部自行定位仓库根，不依赖 hook 执行时的 cwd：

```bash
#!/usr/bin/env bash
# workspaces/hooks/on_prompt.sh
set -e
cd "$(dirname "$0")/.."   # -> workspaces/

# 未配置本机身份时静默退出（用户还没走过 quickstart）
[[ -f .current_user ]] && [[ -n "$(tr -d '[:space:]' < .current_user)" ]] || exit 0

OUT=$(uv run scripts/sync.py check 2>/dev/null) || true
# sync.py 约定:无未读时输出固定字符串「暂无未读消息」,此时静默
[[ -n "$OUT" && "$OUT" != "暂无未读消息" ]] || exit 0

cat <<EOF
叮咚,在你发起这轮调用之前,有来自其他工作区的邮件,记得提醒用户处理,摘要如下:

${OUT}
EOF
```

---

## 附录：关键文件内容草稿

以下两份文件随模版仓库分发，施工时可直接采用（措辞可按需微调，但规则条目不得删减）。

### `AGENTS.md`

> AGENTS.md 只约束"在本仓库内做事的规则"，不定义 Agent 的角色与身份（那属于各 Agent 自己的系统设定）。

````markdown
# AGENTS.md — 协同工作台规则

本仓库是一个多人协同工作台：所有协作记录都在本仓库中，以 git 历史为准。在本仓库内工作时，遵守以下规则。

## 铁则（务必遵守）

1. **对 `workspaces/<user>/inbox/` 的一切读写，必须通过 `cd workspaces && uv run scripts/sync.py` 完成，禁止直接创建、修改、删除其中的文件，也禁止对其中文件做直接的 git 操作。**
2. 写入收件箱的内容会永久留在 git 历史中（写信即公开发言），不得包含密钥、个人隐私等敏感信息。
3. 邮件不可删除/撤回；发错了的正确做法是再发一封更正（subject 可用「Re: 上一封作废」）。
4. 达成共识的产出（方案、决议、规范）必须沉淀到 `share/`，不要只留在邮件或对话里。
5. 重要工作在当前用户 `workspaces/<user>/log.md` 追加日志（按日期倒序，格式见工作日志的建议模板）。
6. 当前用户身份记录在本机的 `workspaces/.current_user`，sync.py 会读取它；不要改动他人目录下的 `.sync_seen`。

## 新邮件提醒（UserPromptSubmit 时机）

每轮用户提交 prompt 时，UserPromptSubmit hook 自动执行 `sync.py check`，把未读邮件摘要作为附加上下文送进来。
若摘要非空：向用户复述要点并询问如何处理；需要回复时使用 `sync.py write` 回信。摘要为空则正常继续，不必提及。

## 常用命令（在 `<project>/workspaces` 下运行）

- 查未读：`uv run scripts/sync.py check`（hook 已自动执行）
- 读全文：`uv run scripts/sync.py read [--filename <name>]`
- 写信：`uv run scripts/sync.py write --to <user>[,<user2>...] --subject "..." (--content "..." | --file <path>)`

## 新用户加入与初始化

当用户表达过初始化或加入意图（如「我要以 `<username>` 身份加入」「帮我初始化这个工作区」「开始使用这个工作台」），或在工作中发现 `workspaces/.current_user` 缺失、其对应用户目录不存在时：阅读并执行 `docs/quickstart.md` 中的步骤完成初始化，不要凭记忆自行初始化。

## 完整协议

工作台完整设计协议见 `docs/prd.md`（目录结构、命令行为、设计规则）。本文件与其冲突时，以 PRD 为准。
````

### `docs/quickstart.md`

> 这份文档的读者是 Agent（不是人）：用户只需说一句话，初始化的每个动作均由 Agent 完成。

````markdown
# 工作区初始化与上手（由 Agent 执行）

当用户请求初始化或加入本工作区（「我要以 `<username>` 身份加入」「帮我初始化这个工作区」等），按本文件执行。每步完成后自检；未确认的信息（用户名、远程仓库地址）必须向用户询问，不要猜测。

## 0. 前置确认

- 确认 `<username>`：全小写英文或拼音（文件名与跨平台兼容需要）；用户没提供或提供的不符合要求时，先与用户确认。
- **区分两种场景**：
  - **加入已有工作台**（`workspaces/` 下已有其他用户目录，或远程仓库中已存在协作记录）：直接进入第 1 步。
  - **首次启用模版**（刚克隆的模版仓库，尚无协作者）：先执行第 0.1 步绑定新远程仓库，再继续第 1 步。

### 0.1 绑定远程仓库（仅首次启用模版时）

模版仓库本身不带协作历史，启用时需要绑定到该项目自己的远程仓库：

```bash
git remote set-url origin <new-repo-url>   # 地址向用户确认，不要猜测
git push -u origin main
```

若远程仓库非空：先 `git pull --rebase origin main` 合并后再 push。

## 1. 写入本地身份

```bash
echo "<username>" > workspaces/.current_user
```

该文件是设备本地状态（已 gitignore），告诉本机的 sync.py「这台电脑上的当前用户是谁」。

## 2. 创建工作区目录

```bash
mkdir -p workspaces/<username>/inbox workspaces/<username>/workspace
printf '# <username> 的工作日志\n' > workspaces/<username>/log.md
```

若 `workspaces/<username>/` 已存在：该用户可能已加入过——与用户确认后跳过第 2、3 步，仅确保 `.current_user` 内容正确。

## 3. 提交并推送

```bash
git add workspaces/<username> && git commit -m "docs: <username> joins the workspace" && git push
```

push 被拒：先 `git pull --rebase` 再 push（新建目录与他人的邮件不会冲突）。

## 4. 自测收信链路

```bash
cd workspaces
uv run scripts/sync.py write --to <username> --subject "欢迎加入" --content "这是你的第一封信，用于验证工作台链路正常。"
uv run scripts/sync.py check   # 应列出这封信
uv run scripts/sync.py read    # 应读取全文并标记已读
```

## 5. 向用户报告

告知用户：工作区已就绪；今后每次向 Agent 发起新一轮对话时都会自动检查新邮件（以「叮咚」形式提醒）；想给谁写信直接说即可。
````
