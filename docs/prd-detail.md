# Message Board PRD

基于 Agent 的多人协同工作台搭建

---

## 🗺️ 读者导航

这份文档同时写给两类人，按你的角色选一条路读：

- **产品经理**：从头读到尾。遇到 🔧 折叠块就跳过——里面是工程师照抄的实现细节，不看也能理解。
- **工程师 / AI**：时间宝贵的话直接跳到 [附录 B：完整技术规范](#附录-b完整技术规范)，一次拿走全部施工图纸；想了解设计取舍再回到正文。

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

**多人同时写信会不会冲突？**——不会。git 的冲突本质是"两个人同时改了同一文件的同一行"。本设计里每封信都是一个**独立的新文件**，文件名带时间戳和发件人，天然不重名；无论多少人同时写信，都只是"仓库里多了几个新文件"，不存在内容冲突。极端情况下，最后一步"把信同步到云端"可能因为"本地落后于云端一个新提交"被拒——投递引擎会自动重新取信再投，最多重试 3 次，超出则报错交还给 Agent（比如稍后重发）。写信的人全程不需要懂 git。

---

## 项目里有什么

这个目录结构不是拍脑袋定的，而是从"多人协作"的需求一步步推导出来的。跟着推导走一遍，每个目录为什么存在就自然明白了：

- **协作首先要有各自的地盘**。多人一起工作，第一要求是隔离：每个人收的信、写的草稿、记的日志都不能和别人混在一起。于是有了 `workspaces/<user>/`——每位协作者一个独立文件夹，互不干扰。
- **各自的地盘之外，还需要一个公共区域**。讨论出的共识（方案定稿、决议）不属于任何个人，必须有个大家都认可的地方沉淀。于是有了 `share/`——共享文件区。
- **协作者之间要通信，信要有去处**。想通知某位同事，得有一个"投到他家门口"的地方。于是每个用户目录下有了 `inbox/`（收件箱）；配套地，写信前的草稿放自己 `workspace/`，每天做过什么记进自己的 `log.md`。
- **信不能只有一种，得讲"公文类型"**。"同步个情况"和"派件活给你"是两种完全不同的事：前者看一眼就过，后者需要应答、需要跟踪闭环。于是信被分成四种公文类型——**邮件**（普通同步）、**协同单**（派活）、**回执**（接受或完成后的应答）、**退回**（不接这单并说明原因）；回执与退回必须带 `ref` 指向原协同单，应答链才断不了。
- **派出去的活要有地方"挂着"**。协同单发出去之后，"这事做到哪一步了"不能靠脑记。于是每个用户目录下有了 `tasks/`（任务包）：一个任务一个文件夹，里面一张 `task.yaml` 记录五态之一（未开始 / 进行中 / 阻塞 / 待确认 / 已完成）和阻塞原因，任务的草稿、产出也随包携带。
- **大家交上来的状态，要有一个"公示栏"**。各自的 inbox 和 tasks 是原始凭证，但"全组现在什么样"需要一个聚合视图。这个聚合只能有一个写手（否则互相覆盖、口径打架），于是引入了 CI 治理：`.github/workflows/board.yml` 充当"邮局分拣中心"，push 后自动聚合、渲染、质检、发布。它的产出有两份：给人和 Agent 在仓库里看的 `board/`（通知台账 + 任务看板，Markdown 版），和对外演示用的 `site/`（审计网页，挂 github.io）。
- **通信和任务动作都不能靠手搓文件**。写信、查信、读信、建任务、改任务状态，如果让每个 AI 自由发挥，格式很快就会乱掉。于是把所有动作收敛到一个投递引擎：`workspaces/scripts/sync.py`。

至此目录结构的骨架已经齐了。但还有两个"让机器转起来"的角色：

- **AI 进门要打卡、要懂规矩**。AI 每轮收到 prompt，得知道"先查一下信箱"，也得知道"收件箱不许直接改"这些铁律。于是有了打卡脚本 `workspaces/hooks/on_prompt.sh`，和给 AI 的入场说明书 `AGENTS.md`。
- **机器得知道"这台电脑上是谁"**。投递引擎查信前，要先知道查谁的收件箱，于是有了机器本地的 `.current_user`；同理，"哪些信读过了"也是机器本地状态，放在每个用户目录下的 `.sync_seen`。

至此目录结构的骨架已经齐了。但还有两个"让机器转起来"的角色：

- **AI 进门要打卡、要懂规矩**。AI 每轮收到 prompt，得知道"先查一下信箱"，也得知道"收件箱不许直接改"这些铁律。于是有了打卡脚本 `workspaces/hooks/on_prompt.sh`，和给 AI 的入场说明书 `AGENTS.md`。
- **机器得知道"这台电脑上是谁"**。投递引擎查信前，要先知道查谁的收件箱，于是有了机器本地的 `.current_user`；同理，"哪些信读过了"也是机器本地状态，放在每个用户目录下的 `.sync_seen`。

整理成一张"需求 → 设计"的对照表：

| 协作需求 | 设计 | 是什么 |
|---|---|---|
| 每人一块地盘 | `workspaces/<user>/` | 某个协作者的独立工作区 |
| 通信要能收信 | `workspaces/<user>/inbox/` | 收件箱：别人写来的信都投在这 |
| 信要分轻重缓急 | 公文类型 + `ref` | 邮件/协同单/回执/退回；回执退回必须挂住原协同单 |
| 派活要能追状态 | `workspaces/<user>/tasks/` | 任务包：一事一包，`task.yaml` 记五态与阻塞 |
| 写信要有草稿区 | `workspaces/<user>/workspace/` | 个人草稿区：写的东西先放这，定稿后再发或沉淀 |
| 工作要留痕迹 | `workspaces/<user>/log.md` | 个人工作日志：按日期倒序记做了什么 |
| 已读状态本地维护 | `workspaces/<user>/.sync_seen` | 已读记录：哪些信看过了 |
| 机器要知道"我是谁" | `workspaces/.current_user` | 本机当前用户：这台电脑上操作的人是谁 |
| 通信与任务动作要统一 | `workspaces/scripts/sync.py` | 投递引擎：写信、查信、读信、任务管理的唯一入口 |
| 全局要有公示栏 | `board/` | 派生区：通知台账 + 任务看板（CI 唯一写手，客户端只读） |
| 对外要能演示审计 | `site/` + github.io | 审计网页：概览/消息/看板三视图的静态站点 |
| 派生只能一家写 | `.github/workflows/board.yml` | CI 治理：聚合→渲染→lint→发布的"邮局分拣中心" |
| AI 进门要打卡 | `workspaces/hooks/on_prompt.sh` | 打卡脚本：AI 每轮提交 prompt 时自动查一下新信 |
| 共识要有家 | `share/` | 共享区：讨论定稿的文件沉淀到这儿 |
| AI 要懂规矩 | `AGENTS.md` | 给 AI 的入场说明书：进仓库要遵守哪些铁律 |
| 新人上手有手册 | `docs/quickstart.md` | 上手指引（给 AI 看，用户说一句"我要加入"，AI 照着做） |
| 设计要有出处 | `docs/prd.md` | 本设计协议（随模版分发一份） |
| 引擎要有测试兜着 | `workspaces/tests/` | pytest：投递、任务、派生函数的回归保障 |
| Claude 专用入口 | `.claude/settings.json`、`CLAUDE.md` | 告诉 Claude Code"进来先打卡、先读 AGENTS.md" |
| Codex 专用入口 | `.codex/hooks.json` | 告诉 Codex"进来先打卡" |
| 本地零碎不进共享 | `.gitignore` | 忽略清单：机器本地文件不进入共享 |
| 工程门面 | `README.md` | 整个工程的说明文件 |

一句话记忆：**workspaces 隔离个人，share 沉淀共识，sync.py 统一通信，tasks 追踪状态，board 与 site 公示全局，CI 端唯一写手，AGENTS.md 管规矩，hook 管打卡**。

<details>
<summary>🔧 技术细节：完整目录树与每一项的用途</summary>

```
<project_name>/             # 工程根目录
├── .claude/settings.json   # Claude UserPromptSubmit hook 配置
├── .codex/hooks.json       # Codex UserPromptSubmit hook 配置
├── .github/workflows/board.yml  # CI 治理 workflow：聚合 → 渲染 → lint → 发布，派生物的唯一写手
├── share                   # 共享文件（达成共识的文件存放位置）
|   └──（自由文件）
├── board/                  # 派生区·Markdown 版（CI 唯一写手，客户端一律只读）
│   ├── ledger/<user>.md    # 每人的通知台账：谁给我投过信、类型、还没读哪些
│   └── task-board.md       # 任务看板：全员工单按状态分列
├── site/                   # 审计网页前端源码（index.html + app.js，无框架原生 JS）
│   └──                     #   说明：data.json 由 CI 生成，与发布产物一样不进 git
├── workspaces
│   ├── .current_user       # 保存了本地的用户是谁
│   ├── <user1>
│   |   ├── inbox/          # <user1> 的收件箱
│   |   ├── tasks/          # <user1> 的任务包（每个任务一个目录，经 sync.py task 管理）
│   |   │   └── <任务名>/
│   |   │       ├── task.yaml   # 任务状态地基（见「使用规则」）
│   |   │       └── ...         # 草稿、产出等自由文件
│   |   ├── .sync_seen      # <user1> 的已读消息记录
|   |   ├── workspace       # <user1> 的个人工作区（草稿区）
|   |   └── log.md          # <user1> 的个人工作日志
│   ├── <user2>
│   |   ├── inbox/          # <user2> 的收件箱
│   |   ├── tasks/          # <user2> 的任务包
│   |   ├── .sync_seen      # <user2> 的已读消息记录
|   |   ├── workspace       # <user2> 的个人工作区（草稿区）
|   |   └── log.md          # <user2> 的个人工作日志
│   ├── scripts/sync.py     # workspaces的CLI 引擎（邮件读、写、检查 + 任务管理）
│   ├── hooks/on_prompt.sh  # UserPromptSubmit hook 的统一入口脚本（自行定位仓库根，不依赖 hook 执行时的 cwd）
│   ├── tests/              # pytest 测试（含台账/看板生成函数用例）
│   ├── pyproject.toml      # uv 项目定义
│   ├── uv.lock             # 依赖锁
│   └── .python-version     # python 3.12
├── docs/prd.md             # 本设计协议（随模版分发，见附录）
├── docs/quickstart.md      # 新协作者的上手步骤（由 Agent 阅读并执行）
├── .gitignore              # 忽略清单（内容见「使用规则」中的约定）
├── AGENTS.md               # Agent 入口指引（含写入铁则），需要写清楚整个工作区的运转机制，并引用 docs/quickstart.md
├── CLAUDE.md → AGENTS.md   # 软链接（Claude Code）
└── README.md               # 整个工程的README.md文件
```

</details>

---

## 使用规则

前面说的是"有什么"，这一节说"怎么用、守什么规矩"。规则分两层：**四个动作**（写信、查信、读信、管任务——所有沟通与派活都收敛到这四个动作上）和**一组场地规矩**（每个目录能干嘛、不能干嘛）。

### 四个动作

用户的所有沟通与任务推进，最终都被 Agent 翻译成以下四个动作之一。理解这四个动作，就理解了整个产品。

#### 动作一：写信（write）

用户只要对 Agent 说一句"跟张三说一下明早的评审改到下午"，Agent 就会执行写信动作：把这句话整理成一封信，投进张三的收件箱，同步到云端。

我们给写信定了几条规矩：

- **信分四种公文类型**。**邮件**（默认）：同步情况、发通知，看一眼就过；**协同单**：正式派活给对方，需要应答；**回执**：接受协同单或完成后的应答；**退回**：不接这单，说明原因。类型写在信头上，台账、看板、审计网页都按它分账。
- **应答必须挂住原单（ref）**。回执和退回必须带上 `--ref` 指向自己收件箱里那张协同单——链不上就直接拒发。这样每张单的"派出 → 应答"成对可查，谁答应了、谁退回了、为什么，全程可追溯。
- **先取信再投信**。动笔前先把云端的最新内容拉下来，避免在旧版本上工作。
- **一封信可以同时寄给多人**。同一封信会分别投进每个收件人的收件箱。
- **投递失败自动重试，但有上限**。极端情况下"投完信同步云端"会被拒（原因：别人抢先同步了新东西），投递引擎会自动重新拉取再同步，最多重试 3 次；超出就报错，交还给 Agent 决定稍后重发——不会无限死磕。
- **信写出去就不能撤回**。这一点下一节"场地规矩"里详细说。

<details>
<summary>🔧 技术细节：write 命令规范</summary>

`uv run scripts/sync.py write --to {userx},{usery} [--content {md_content} | --file {filename}] --subject {subject} [--type {类型}] [--ref {原单文件名}]`（运行方式统一为：先 `cd <project>/workspaces`，再 `uv run scripts/sync.py ...`；`uv run` 从当前目录向上发现 `pyproject.toml`，使用 `workspaces/.venv` 环境）

- `--type` 合法值：`邮件`（默认，不传时等同）/ `协同单` / `回执` / `退回`，写入 frontmatter 的 `type` 字段。协同单 = 派活给对方；回执 = 接受或完成后的应答；退回 = 不接这单并说明原因。
- `--type 回执` 与 `--type 退回` 必须同时传 `--ref {原单文件名}`（指向自己收件箱里那张协同单的文件名），写入 frontmatter 的 `ref` 字段，以此保证每张单的应答链可追溯；`--ref` 指向的文件在本人 inbox 中不存在时，直接报错退出，不发信。
- `--content` 与 `--file` 二选一：`--content` 直接传邮件正文文本；`--file` 从文件读取正文。**`--file` 的路径支持绝对路径与相对路径**（相对路径按命令执行时的当前工作目录解析，与 `cat`/`cp` 等 Unix 命令一致）——邮件正文文件可以在仓库之外（例如 Agent 在 `/tmp` 起草的中间稿），只有最终生成的收件箱文件才进入版本库。

执行步骤：

1. 执行 `git pull`
2. 基于 {subject} 和 {md_content}（或 {filename} 中读取的内容）构建 markdown 文件，格式为：

````markdown
---
from: {.current_user}
to:
  - {userx}
  - {usery}
date: YYYY-MM-DD HH:mm:ss Z   # Z 为 UTC 偏移，如 +0800（对应 Python strftime: %Y-%m-%d %H:%M:%S %z）
subject: {subject}
type: 邮件 | 协同单 | 回执 | 退回   # 不传 --type 时写「邮件」
ref: {原单文件名}   # 仅 回执/退回 时存在
---
{md_content（或者是 {filename} 中读取出来的内容）}
````

3. 对 `--to` 中的每个收件人，分别将该 markdown 文件写入 `workspaces/{每个收件人}/inbox/YYYY-MM-DD-HH-mm-ss-Z-{.current_user}.md`（内容相同，文件名相同；Z 为 UTC 偏移如 `+0800`，在文件名中合法）
4. 执行 `git add -> git commit -m "docs: {.current_user} sends a message to {userx},{usery}" -> git push`（commit message 中列出所有收件人）

> 极端情况：若在步骤 1（`git pull`）之后、步骤 4（`git push`）之前，其他用户推了新提交导致 push 被拒，必须重新 `git pull` 合并后再 push；**最多自动重试 3 次**，超出则报错退出，交还给调用方（Agent）决定稍后重发。

约定：`{.current_user}` 表示**读取 `workspaces/.current_user` 文件内容得到的用户名**（去掉首尾空白），sync.py 启动时读取一次；若文件不存在或为空，应报错并提示先写入当前用户名。

</details>

#### 动作二：查信（check）

这是 Agent 每次"上班打卡"时做的动作：看一下你的收件箱里有没有还没读的信，有就列个清单给你——谁发的、什么时候、什么事。它只是"列清单"，打开信不算读过。

查信结果后面还会附一小段**任务现状**：你手头有几件事在进行中、几件事被卡住、各自在等什么。这样 AI 每天一打卡，既能呈上新信，也能提醒你"上次接的活还没动"。

<details>
<summary>🔧 技术细节：check 命令规范</summary>

`uv run scripts/sync.py check [--fmt json | markdown]`（默认以 markdown 格式输出）

1. 执行 `git pull`
2. 检查 `workspaces/{.current_user}/inbox` 中所有未读消息（对照 `.sync_seen` 判断已读），按格式输出
   - `--fmt json`：

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

   - markdown 格式：

```markdown
|发件人|收件人|日期|标题|
|-----|-----|---|----|
|from | to |date|subject|
```

3. 追加「任务现状」段：统计 `workspaces/{.current_user}/tasks/` 下状态为「进行中」「阻塞」的任务；有阻塞时逐条列出 blocked_by。markdown 示例：

```markdown
## 任务现状
- 进行中 2 件 / 阻塞 1 件
- 阻塞：下单锁库存联调（等 mingyi 回执）
```

   json 输出增加 `tasks: {in_progress: [...], blocked: [{name, blocked_by}]}`

4. 无未读邮件且「任务现状」为空时，维持原有约定输出固定字符串「暂无未读消息」（入口脚本据此静默）

</details>

#### 动作三：读信（read）

打开一封信看全文。看过之后，这封信会在你的已读记录里登记，下次"查信"就不再列它了。也可以指定只读某一封（比如刚才清单里的第三封）。

<details>
<summary>🔧 技术细节：read 命令规范</summary>

`uv run scripts/sync.py read [--filename {filename}]`

1. 执行 `git pull`
2. 未指定 {filename}：读取 `workspaces/{.current_user}/inbox` 中所有未读消息（`.sync_seen` 中记录了哪些已读），并将这些消息记入 `.sync_seen` 标记为已读；指定 {filename} 时，直接读取 `workspaces/{.current_user}/inbox/{filename}` 这一封。

</details>

#### 动作四：管任务（task）

信是"沟通"，任务就是"沟通之后的活"。协同单接下来了，总得有个地方挂着它、追到它闭环。**任务包**就是干这个的：一个任务一个文件夹（在自己目录的 `tasks/` 下），里面一张 `task.yaml` 记录状态，还有这个任务的草稿、产出文件。

任务的状态被收敛成**五态**——这是它和看板、审计网页对齐的"普通话"，谁都不能造第六个词：

| 状态 | 含义 | 什么时候用 |
|---|---|---|
| 未开始 | 接了单还没动工 | 刚建任务时默认就是它 |
| 进行中 | 正在做 | 动工了 |
| 阻塞 | 卡住了，在等别人 | 配合 `blocked_by` 写清"等什么"，如「等 bob 回执」 |
| 待确认 | 自认为做完了，等对方确认 | 交付了协同单要的产出 |
| 已完成 | 对方确认收下，闭环 | 收到回执后收尾 |

规矩和收件箱类似：**状态变更必须通过投递引擎**（`sync.py task create / update`），只能动自己目录下的任务包；包里 `task.yaml` 以外的一切（草稿、产出）自由编辑、引擎不管。任务从哪里来？通常是一张协同单——建任务时可以用 `--from` 记下游单，这样"哪张单派出了哪个活"也能对上。

<details>
<summary>🔧 技术细节：task 命令规范与 task.yaml</summary>

建任务 `uv run scripts/sync.py task create --name {任务名} [--from {协同单文件名}]`：

1. 执行 `git pull`
2. 创建 `tasks/{任务名}/` 目录并写入 `task.yaml`（status 初始为「未开始」；传了 --from 则记录上游协同单路径）
3. 同名目录已存在时报错退出（提示先 `task list` 看现状）
4. 执行 `git add -> commit -> push`

更新任务 `uv run scripts/sync.py task update --name {任务名} [--status {状态}] [--blocked {阻塞说明}]`：

1. 执行 `git pull`；任务不存在时报错退出
2. `--status` 只允许五态之一：`未开始 / 进行中 / 阻塞 / 待确认 / 已完成`，传其他值报错退出并列出合法值
3. 更新 `task.yaml` 的 status / blocked_by，`updated` 自动落当天日期
4. 执行 `git add -> commit -> push`

列任务 `uv run scripts/sync.py task list [--fmt json | markdown]`：列本人全部任务包及各自状态。

`task.yaml` schema（任务状态的唯一地基）：

```yaml
task: 下单锁库存联调
from: inbox/2026-09-03-10-00-00-+0800-bob.md   # 上游协同单，没有则写「无」
status: 进行中      # 五态：未开始 / 进行中 / 阻塞 / 待确认 / 已完成
blocked_by: 无      # status 为「阻塞」时写等什么，如「等 bob 回执」
updated: 2026-09-03
```

只能在自己目录下建/改任务；他人 `workspaces/<user>/` 一切只读。任务状态词汇必须收敛到五态——聚合看板依赖枚举一致性，手写第六个词会被 CI lint 标红。刻意不做「收工四件套」式的纪律（过程记录、日志强制四连）：log.md 维持现有手工约定，不加重。

</details>

---

### 场地规矩

前面说的是动作，这一节说场地的规矩——每个目录/文件是干什么的、谁能碰。

**收件箱（每个人的 `inbox/`）** —— 全仓库最神圣的地方，有两条铁律：

- **不许绕过投递引擎直接改**。不管是人还是 Agent，都必须通过"投递引擎"（`sync.py`）来写。这是底线，破坏就乱套了。
- **信不能删，也不能撤回**。寄出去的信就是历史；发错了的正确处置是**再写一封更正**（比如主题写「Re: 上一封作废」）。这就是"工程即记录系统"的硬核部分——历史不可虚构。
- **所以写信时请注意**：信一旦寄出，会永久留在 git 历史里，所有协作者都能看到。千万别把密钥、个人隐私等敏感信息写进信里。

**共享区（`share/`）** —— 讨论定稿后放结论的地方，全仓库最自由的地方：

- 所有协作者都可以自由读写，不受"必须通过投递引擎"的限制
- **只有达成共识的产物才放这里**（方案定稿、决议、规范），别把半成品往里塞——草稿请放自己的 `workspace/`

**个人草稿区（`workspace/`）** —— 你的自留地，随意。

**工作日志（`log.md`）** —— 记你做了什么，建议**按日期倒序写，新内容加在最上面**（这样多人同时写不易冲突）。

<details>
<summary>🔧 技术细节：附录原章节没改动，日志格式建议如下</summary>

```markdown
# alice 的工作日志

## 2026-08-30
- 与 bob 讨论了登录方案选型（详见 inbox/2026-08-30-10-00-00-+0800-bob.md）
- 共识已沉淀至 share/auth-design.md

## 2026-08-29
- ...
```

</details>

**机器本地状态**.`workspaces/` 下有两类文件是**每台机器各自维护、不进共享**的：

- `.current_user`：本机是谁（你 clone 完仓库后第一时间写进去）
- `.sync_seen`：你读到哪了

这两个文件不进 git（在 `.gitignore` 里），换台机器就重新生成，不同步——同步反而会乱（A 机器读了信，B 机器就看不到提醒了）。

<details>
<summary>🔧 技术细节：.gitignore 规范</summary>

```gitignore
# Python / uv 环境
workspaces/.venv/
__pycache__/

# 设备本地状态（每台机器各自维护）
workspaces/.current_user
workspaces/*/.sync_seen

# 系统杂物
.DS_Store
```

</details>

**新手怎么上手？**——你几乎不用动手。你只要：

1. 下载（clone）这个工程
2. 对你的 Agent 说一句"我要以 xxx（全小写英文或拼音）身份加入"

剩下所有事——写入用户名、建收件箱、建草稿区、记第一笔日志、同步云端、发一封欢迎信给自己验证链路——**全部由 Agent 照着手册做完**。手册就是 `docs/quickstart.md`，是给 AI 看的，不是给你看的；但你要信任它（我们让 Agent 必须引用它，不许凭记忆自由发挥）。

**用户名约定**：全小写英文或拼音（避免中文名在文件名、git、跨平台兼容上的坑）。

---

## 公示栏与审计网页：全局视图从哪来

到这一步，每个协作者的信和任务都规规矩矩躺在仓库里了。但**站在全组视角看"现在什么样"**，还需要一层东西——这就是 `board/`（派生区）和 `site/`（审计网页）要解决的问题。

**通知台账有什么用？** 想象你是团队的 PM，你想知道的不是"alice 的 inbox 里有哪 37 个文件"，而是：还有哪些协同单没人应答？谁手头阻塞最多？这周跨组的往来密不密？通知台账（`board/ledger/<user>.md`）就是把每个人的收件箱元数据按人装订成册——谁给我投过信、什么类型、日期、挂的是哪张单、还没读哪些。它不是新信息，而是把散落各处的原始凭证**聚合成能一眼扫读的"公文流转总账"**。任务看板（`board/task-board.md`）同理：把全组的 `task.yaml` 按五态分列排开。

**谁来写这个公示栏？——只有 CI。** 这是权责设计上很硬的一条：派生区是"读模型"，原始凭证（inbox、task.yaml）才是"写模型"。如果允许每个客户端自己也去改台账，口径必然打架。所以我们让 GitHub Actions（`board.yml`）当唯一的"邮局分拣中心"：push 到 main 后自动做五步——**聚合**（扫全部信头与任务）→ **渲染 Markdown 派生区** → **渲染网页数据** → **lint 质检**（绕过引擎写信、状态造出第六个词、手改派生区，一律标红但不动文件）→ **发布**（Markdown 回提仓库、网页挂上 github.io）。代价是 30~90 秒延迟；审计看的是"发生过什么"，分钟级延迟完全可以接受，秒级实时不是这个架构的目标。

**审计网页（github.io）是本系统的对外主视图。** 它和 Markdown 台账共用同一份聚合数据（`data.json`），但穿上了一件"给演示和审计看"的外衣，三个视图：

- **全局概览**：信件流通总量、协同单闭环率、活跃任务、受阻事项——演示时开场先把这张甩出来
- **消息审计**：全部公文的收发流水与 ref 应答链，可按类型筛选
- **任务看板**：全员任务五态分列，阻塞项标明被什么卡住

网页只展示元数据（谁发给谁、什么类型、什么状态），不含信件正文；正文回仓库看。这样做还有个现实好处：**github.io 托管的是脱敏后的聚合产物**，原始讨论内容不离开仓库。

<details>
<summary>🔧 技术细节：CI 流程、派生区与审计网页规范</summary>

**CI 治理（`.github/workflows/board.yml`）**——托管仓没有服务端 hook，用它顶替「邮局分拣中心」

- 触发：push 到 main；防环条件 `if: github.actor != 'github-actions[bot]'`
- 五个步骤：
  1. **聚合**：扫所有 inbox frontmatter + 所有 task.yaml → 生成聚合数据（Python 函数，与 sync.py 共用）
  2. **渲染 Markdown**：聚合数据 → `board/ledger/<user>.md` + `board/task-board.md`
  3. **渲染网页产物**：聚合数据 → `data.json`；与 `site/` 静态前端一起打成 Pages 产物（yaml 解析失败的任务照常进数据、缺字段留空，不让单个坏文件阻塞构建）
  4. **lint**：发现违规即 workflow 失败标红，但不改任何文件：
     - 非 sync.py 提交记录中改动了 `workspaces/*/inbox/`（绕过投递引擎）
     - `task.yaml` 的 status 不在五态枚举内
     - 非 board-bot 提交改动了 `board/`
  5. **发布**：Markdown 产物如有变化，以 board-bot 身份提交回仓库（commit message 前缀固定 `[board-bot]`，push 撞车 `git pull --rebase` 重试一次）；网页产物 `deploy-pages` 发布上线
- 现实妥协（写进文档让人知情）：延迟 30~90 秒（Actions 排队），换来派生区绝对单写；lint 只能事后标红，做不到自建 git pre-receive 那种当场拦截；不强开 branch protection，以免「每写一封信都要等 CI 绿」

**派生区（`board/`）**——CI 唯一写手，客户端一律只读

- `board/ledger/<user>.md`（通知台账）：由 CI 从各用户 inbox 的 frontmatter 派生，按时间倒序列出每封信的发件人、日期、type、subject、ref 链路
- `board/task-board.md`（任务看板）：由 CI 聚合所有 `workspaces/*/tasks/*/task.yaml`，按五个状态分列，每行含任务名、owner、from 上游、blocked_by
- 派生文件的境地：改了也没用——下次 CI 重建会被覆盖；本地修改 board/ 属 lint 违规
- 台账与看板是「读模型」：丢失可随时从 inbox + task.yaml 全量重建，无独立信息价值

**审计网页（github.io 静态站点）**——数据与 Markdown 版同源

- 产物三件套（由 `board.yml` 生成，经 `actions/upload-pages-artifact` + `actions/deploy-pages` 发布，**不进 git 仓库**）：
  1. `data.json`：全量审计数据——所有信件的 frontmatter 元数据 + 所有任务
  2. `site/index.html`：单页应用入口，自包含样式
  3. `site/app.js`：原生 JS，无框架；fetch 一律用相对路径（站点挂在 `/message-board/` 子路径下，绝对路径会 404）；`data.json` 加载失败时回退内置演示数据 `MOCK_DATA`，保证本地双击也能完整预览
- 前置手工步骤（仅一次）：仓库 Settings → Pages → Source 选 "GitHub Actions"

</details>

---

## AI 的"上班打卡"机制（Hook）

**问题**：你怎么让 Agent 每天开始工作时，主动帮你查信箱？

**答案**：我们给 Claude Code 和 Codex 各贴了一张"打卡条"——告诉它"每次用户提交 prompt 时，先运行一遍查信命令"，这张条就是 **Hook**（用户提交通知钩子）。

打卡规则一次配置，永久生效；打卡的内容、命令都封装在 `sync.py check` 里，AI 只是照章执行。

**两个细节值得一提**：

- 打卡脚本放在仓库里，与代码同更新——任何人 clone 下来就能直接用，不用关心自己的绝对路径是什么。
- 为了保证不同 Agent 的打卡行为一致，我们让 Claude 和 Codex 都指向**同一个入口脚本**内部跑 `sync.py check`，而不是让两家各执一词。

<details>
<summary>🔧 技术细节：完整 Hook 配置</summary>

Claude 与 Codex 的 UserPromptSubmit hook 都指向同一个入口脚本 `workspaces/hooks/on_prompt.sh`（已提交进仓库），不在 hook 配置里写绝对路径，因此每个协作者 clone 到任意路径都无需修改配置。

每次用户提交 prompt，hook 都会自动跑一次 `sync.py check`。若收件箱为空、无未读邮件，入口脚本静默退出（exit 0、零输出），不打断用户与 Agent 的对话；若有未读邮件，脚本以「叮咚」形式把摘要包装后输出，Claude Code / Codex 会把这段输出作为附加上下文注入当轮对话，使 Agent 知道"有新邮件到了"。

`.claude/settings.json`：

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

`.codex/hooks.json`：

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

</details>

---

## 附录 A：给 AI 的两份说明书（草稿）

到这里，PM 读者已经掌握了产品的全部。下面两份文件是**给 AI 看的指令书**——`AGENTS.md` 和 `docs/quickstart.md`。我们把它们的草稿一并放进这份 PRD，因为**它们是"产品需求"的一部分**：一个协作系统里，给 AI 的说明书和给人的界面同等重要。

如果你是 PM，可以浏览一下看看"我们是怎么向 AI 描述这套规矩的"，注意它们一硬一软的分工：

- **AGENTS.md**（硬规则）：列铁律——"不能绕过投递引擎"、"信不能删"、"私密别写进来"。语气严肃，条款式。
- **docs/quickstart.md**（软指引）：教 Agent 怎么帮新用户完成初始化。语气操作化，步骤式。

如果你是工程师，这两份文件随模版仓库一起分发，措辞可按需微调，但**规则条目不得删减**。

<details>
<summary>📄 AGENTS.md 草稿（点击展开）</summary>

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
7. `board/` 是 CI 自动重建的派生区，只读不改。
8. 任务状态变更一律用 `sync.py task` 完成；只能动自己 `workspaces/<自己>/` 下的文件，他人目录一律只读。

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

工作台完整设计协议见 `docs/prd.md`（目录结构、命令行为、设计规则）。本文件与其冲突时，以 PRD 为准。
````

</details>

<details>
<summary>📄 docs/quickstart.md 草稿（点击展开）</summary>

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

</details>

---

## 附录 B：完整技术规范

工程师/AI 用于一次拿走全部施工图纸。以下为 `docs/prd.md` 原文的完整拷贝，截至本次撰写。

``````markdown
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
├── .github/workflows/board.yml  # CI 治理 workflow：聚合 → 渲染 → lint → 发布，派生物的唯一写手
├── share                   # 共享文件（达成共识的文件存放位置）
|   └──（自由文件）
├── board/                  # 派生区·Markdown 版（CI 唯一写手，客户端一律只读）
│   ├── ledger/<user>.md    # 每人的通知台账：谁给我投过信、类型、还没读哪些
│   └── task-board.md       # 任务看板：全员工单按状态分列
├── site/                   # 审计网页前端源码（index.html + app.js，无框架原生 JS）
│   └──                     #   说明：data.json 由 CI 生成，与发布产物一样不进 git
├── workspaces
│   ├── .current_user       # 保存了本地的用户是谁
│   ├── <user1>
│   |   ├── inbox/          # <user1> 的收件箱
│   |   ├── tasks/          # <user1> 的任务包（每个任务一个目录，经 sync.py task 管理）
│   |   │   └── <任务名>/
│   |   │       ├── task.yaml   # 任务状态地基（见「设计规则」）
│   |   │       └── ...         # 草稿、产出等自由文件
│   |   ├── .sync_seen      # <user1> 的已读消息记录
|   |   ├── workspace       # <user1> 的个人工作区（草稿区）
|   |   └── log.md          # <user1> 的个人工作日志
│   ├── <user2>
│   |   ├── inbox/          # <user2> 的收件箱
│   |   ├── tasks/          # <user2> 的任务包
│   |   ├── .sync_seen      # <user2> 的已读消息记录
|   |   ├── workspace       # <user2> 的个人工作区（草稿区）
|   |   └── log.md          # <user2> 的个人工作日志
│   ├── scripts/sync.py     # workspaces的CLI 引擎（邮件读、写、检查 + 任务管理）
│   ├── hooks/on_prompt.sh  # UserPromptSubmit hook 的统一入口脚本（自行定位仓库根，不依赖 hook 执行时的 cwd）
│   ├── tests/              # pytest 测试（含台账/看板生成函数用例）
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
  - 写 `uv run scripts/sync.py write --to {userx},{usery} [--content {md_content} | --file {filename}] --subject {subject} [--type {类型}] [--ref {原单文件名}]`：
    - `--type` 合法值：`邮件`（默认，不传时等同）/ `协同单` / `回执` / `退回`，写入 frontmatter 的 `type` 字段。协同单 = 派活给对方；回执 = 接受或完成后的应答；退回 = 不接这单并说明原因
    - `--type 回执` 与 `--type 退回` 必须同时传 `--ref {原单文件名}`（指向自己收件箱里那张协同单的文件名），写入 frontmatter 的 `ref` 字段，以此保证每张单的应答链可追溯；`--ref` 指向的文件在本人 inbox 中不存在时，直接报错退出，不发信
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
    type: 邮件 | 协同单 | 回执 | 退回   # 不传 --type 时写「邮件」
    ref: {原单文件名}   # 仅 回执/退回 时存在
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
    3. 追加「任务现状」段：统计 `workspaces/{.current_user}/tasks/` 下状态为「进行中」「阻塞」的任务；有阻塞时逐条列出 blocked_by。markdown 示例：
      ```markdown
      ## 任务现状
      - 进行中 2 件 / 阻塞 1 件
      - 阻塞：下单锁库存联调（等 mingyi 回执）
      ```
      json 输出增加 `tasks: {in_progress: [...], blocked: [{name, blocked_by}]}`
    4. 无未读邮件且「任务现状」为空时，维持原有约定输出固定字符串「暂无未读消息」（入口脚本据此静默）
  - 任务管理 `task` 子命令组（操作本人 `workspaces/{.current_user}/tasks/` 下的任务包）：
    - 建任务 `uv run scripts/sync.py task create --name {任务名} [--from {协同单文件名}]`：
      1. 执行 `git pull`
      2. 创建 `tasks/{任务名}/` 目录并写入 `task.yaml`（status 初始为「未开始」；传了 --from 则记录上游协同单路径）
      3. 同名目录已存在时报错退出（提示先 `task list` 看现状）
      4. 执行 `git add -> commit -> push`
    - 更新任务 `uv run scripts/sync.py task update --name {任务名} [--status {状态}] [--blocked {阻塞说明}]`：
      1. 执行 `git pull`；任务不存在时报错退出
      2. `--status` 只允许五态之一：`未开始 / 进行中 / 阻塞 / 待确认 / 已完成`，传其他值报错退出并列出合法值
      3. 更新 `task.yaml` 的 status / blocked_by，`updated` 自动落当天日期
      4. 执行 `git add -> commit -> push`
    - 列任务 `uv run scripts/sync.py task list [--fmt json | markdown]`：列本人全部任务包及各自状态
    - 任务包内 `task.yaml` 以外的文件（草稿、产出等）为自由文件，sync.py 不管


- **任务包（`workspaces/<user>/tasks/<任务名>/`）**
  - 任务名即目录名，与 `task.yaml` 的 `task` 字段一致
  - `task.yaml` 是任务状态的唯一地基，schema 如下：
    ```yaml
    task: 下单锁库存联调
    from: inbox/2026-09-03-10-00-00-+0800-bob.md   # 上游协同单，没有则写「无」
    status: 进行中      # 五态：未开始 / 进行中 / 阻塞 / 待确认 / 已完成
    blocked_by: 无      # status 为「阻塞」时写等什么，如「等 bob 回执」
    updated: 2026-09-03
    ```
  - `task.yaml` 只通过 `sync.py task create / update` 变更；包内其余文件自由编辑
  - 只能在自己目录下建/改任务；他人 `workspaces/<user>/` 一切只读
  - 任务状态词汇必须收敛到五态——聚合看板依赖枚举一致性，手写第六个词会被 CI lint 标红
  - 刻意不做「收工四件套」式的纪律（过程记录、日志强制四连）：log.md 维持现有手工约定，不加重

- **派生区（`board/`）**——CI 唯一写手，客户端一律只读
  - `board/ledger/<user>.md`（通知台账）：由 CI 从各用户 inbox 的 frontmatter 派生，按时间倒序列出每封信的发件人、日期、type、subject、ref 链路
  - `board/task-board.md`（任务看板）：由 CI 聚合所有 `workspaces/*/tasks/*/task.yaml`，按五个状态分列，每行含任务名、owner、from 上游、blocked_by
  - Markdown 版的读者是 clone 仓的人和 Agent；网页是另一份渲染产物（见「审计网页」），两者共用同一份聚合数据，口径永远一致
  - 派生文件的境地：改了也没用——下次 CI 重建会被覆盖；本地修改 board/ 属 lint 违规
  - 台账与看板是「读模型」：丢失可随时从 inbox + task.yaml 全量重建，无独立信息价值

- **审计网页（github.io 静态站点）**——本系统的对外主视图，数据与 Markdown 版同源
  - 产物三件套（由 `board.yml` 在 CI 内生成，经 `actions/upload-pages-artifact` + `actions/deploy-pages` 发布到 GitHub Pages，**不进 git 仓库**——仓库历史只留人写的东西，生成物活在 CI 产物与 Pages 托管层）：
    1. `data.json`：全量审计数据——所有信件的 frontmatter 元数据（from/to/date/subject/type/ref）+ 所有任务（task 名/owner/status/blocked_by/updated/from），Markdown 台账与看板也由它二次渲染
    2. `site/index.html`：单页应用入口，自包含样式
    3. `site/app.js`：原生 JS，无框架（演示系统要能离线读源码）；fetch 一律用相对路径（站点挂在 `/message-board/` 子路径下，绝对路径会 404）
  - 三个视图（底部浮动 Tab 切换，URL Hash 深链 `#view=stats|messages|kanban`）：
    - **全局概览**：信件流通总量、协同单闭环率、活跃协作任务、受阻事项四张统计卡，外加「任务五态分布」「协作活跃度排行（收发信件）」两组横向条形图——给演示的总览开场用
    - **消息审计**：全部信件元数据流水列表，可按公文类型（邮件/协同单/回执/退回）筛选，行内显示 ref 应答链引用
    - **任务看板**：五态分列的全员任务，阻塞项显示 blocked_by 依赖；每列在任务过多时列内独立滚动，列高占满当前视口
  - 视觉与交互规范（已在 `site/index.html` 原型落地，后续演进以此为准）：
    - 基调：Apple 式排版骨架（系统字体栈、大留白、圆角卡片、1px 半透明细线）+ **宣纸底色** `#f5f0e4`，卡片用亮半度的纸色 `#fdfbf5`，看板列用深一档纸色 `#efe8d8`
    - 点缀色取低饱和传统色：朱砂 `#b03a2e`（受阻/危险）、黛蓝 `#3a5a7b`（邮件/主强调）、松绿 `#4a7a5e`（已完成）、赭石 `#b07d2b`（阻塞/退回）、紫檀 `#7d5a78`（回执/ref 引用）、藤黄 `#c9a227`（待确认）、墨灰 `#8a8474`（未开始）
    - 布局：顶栏 = 品牌（Message Board · Audit View）+ 居中抬头「多人协作工作台 · Dashboard」+ 数据快照时间；导航是底部居中的**浮动胶囊 Tab**（毛玻璃、吸底）；页面铺满视口高度；`prefers-reduced-motion` 下关闭动效
    - 数据：`data.json` 加载失败时回退到内置演示数据（`app.js` 的 `MOCK_DATA`），保证本地双击 `index.html` 也能完整预览交互
  - 页面只含元数据，不含信件正文；正文回仓库看
  - 前置手工步骤（仅一次）：仓库 Settings → Pages → Source 选 "GitHub Actions"，地址为 `https://<owner>.github.io/<repo>/`
  - 延迟预期：**push 后约 30~90 秒网页更新**（Actions 排队是大头）。审计系统看的是"发生过什么"，分钟级延迟可接受；秒级实时不是这个架构的目标，不要追

- **CI 治理（`.github/workflows/board.yml`）**——托管仓没有服务端 hook，用它顶替「邮局分拣中心」
  - 触发：push 到 main；防环条件 `if: github.actor != 'github-actions[bot]'`
  - 五个步骤：
    1. **聚合**：扫所有 inbox frontmatter + 所有 task.yaml → 生成聚合数据（Python 函数，与 sync.py 共用）
    2. **渲染 Markdown**：聚合数据 → `board/ledger/<user>.md` + `board/task-board.md`
    3. **渲染网页产物**：聚合数据 → `data.json`；与 `site/` 静态前端一起打成 Pages 产物（yaml 解析失败的任务照常进数据、缺字段留空，不让单个坏文件阻塞构建）
    4. **lint**：发现违规即 workflow 失败标红，但不改任何文件：
       - 非 sync.py 提交记录中改动了 `workspaces/*/inbox/`（绕过投递引擎）
       - `task.yaml` 的 status 不在五态枚举内
       - 非 board-bot 提交改动了 `board/`
    5. **发布**：Markdown 产物如有变化，以 board-bot 身份提交回仓库（commit message 前缀固定 `[board-bot]`，push 撞车 `git pull --rebase` 重试一次）；网页产物 `deploy-pages` 发布上线
  - 现实妥协（写进文档让人知情）：
    - 延迟：push 后约 30~90 秒台账/看板/网页才更新（Actions 排队），换来派生区绝对单写
    - lint 只能事后标红，做不到自建 git pre-receive 那种当场拦截；不强开 branch protection，以免「每写一封信都要等 CI 绿」

- **测试（`workspaces/tests/`）**——pytest，fixture 用临时目录 `git init` 的空仓当 origin
  - write 带 `--type`/`--ref` 的 frontmatter 正确性；`--ref` 文件不存在时的拒绝路径
  - task create / update / list 正常流；非法状态值拒绝；同名任务重复创建拒绝
  - check 的「任务现状」段输出；全静默场景
  - 台账/看板/data.json 生成函数：喂伪造的 inbox + tasks，断言分簿、分列、JSON schema、坏 yaml 降级正确（生成函数由 sync.py 与 board.yml 共用同一份代码）

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
7. `board/` 是 CI 自动重建的派生区，只读不改。
8. 任务状态变更一律用 `sync.py task` 完成；只能动自己 `workspaces/<自己>/` 下的文件，他人目录一律只读。

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
printf '# <username> 的工作日志
' > workspaces/<username>/log.md
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
``````
