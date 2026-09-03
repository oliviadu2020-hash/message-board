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
│   ├── ledger/<user>.md    # 每人的收件流水台账：时间/发件人/类型/标题/ref（不含已读状态——已读在本地 .sync_seen）
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
│   ├── scripts/derive.py   # 派生渲染引擎：聚合 inbox+task.yaml → board/ 台账与看板、data.json（与 CI 共用）
│   ├── scripts/derive_lint.py  # CI lint 规则（绕过引擎写 inbox / status 出五态 / 非 board-bot 改 board）
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
    ref: {原单文件名}   # 传了 --ref 就写入；回执/退回 由引擎强制校验必须带
    ---
    {md_content(或者是{filename}中读取出来的内容)}
    ```
    3. 对 `--to` 中的每个收件人，分别将该 markdown 文件写入到 `workspaces/{每个收件人}/inbox/YYYY-MM-DD-HH-mm-ss-Z-{.current_user}.md` 中（内容相同，文件名相同；Z 为 UTC 偏移如 `+0800`，在文件名中合法）
    4. 执行`git add -> git commit -m "docs: {.current_user} sends a message to {userx},{usery}" -> git push`（commit message 中列出所有收件人）
    > 极端情况：若在步骤 1（`git pull`）之后、步骤 4（`git push`）之前，其他用户推了新提交导致 push 被拒，必须重新 `git pull` 合并后再 push；**最多自动重试 3 次**，超出则报错退出，交还给调用方（Agent）决定稍后重发。
  - 检查 `uv run scripts/sync.py check [--fmt json | markdown(默认以markdown格式输出)]`：
    1. 执行git pull
    2. 检查`workspaces/{.current_user}/inbox`中所有未读消息，然后按照格式进行输出
    3. 输出结构：
      - `--fmt json` 顶层对象含 `messages`（未读消息数组）与 `tasks`（任务现状）两键：
      ```json
      {
        "messages": [
          {
            "from": "xxx",
            "to": ["userx", "usery"],
            "date": "YYYY-MM-DD HH:mm:ss Z",
            "subject": "这里是一段简介",
            "type": "邮件",
            "ref": null
          }
        ],
        "tasks": {
          "in_progress": ["任务甲"],
          "blocked": [{"name": "任务乙", "blocked_by": "等 bob 回执"}]
        }
      }
      ```
      - `--fmt markdown` 先输出未读信件表（列：发件人/收件人/日期/类型/标题，回执与退回在标题后附 ` ↩ ref`），再在文末追加「任务现状」段：
      ```markdown
      |发件人|收件人|日期|类型|标题|
      |-----|-----|---|----|----|
      |bob |alice|2026-09-03 10:00:00 +0800|协同单|请核对数据|
      |bob |alice|2026-09-03 11:00:00 +0800|回执|已接受 ↩ 2026-09-03-10-00-00-+0800-bob.md|
      ```
    4. 「任务现状」段：统计 `workspaces/{.current_user}/tasks/` 下状态为「进行中」「阻塞」的任务；有阻塞时逐条列出 blocked_by：
      ```markdown
      ## 任务现状
      - 进行中 2 件 / 阻塞 1 件
      - 阻塞：下单锁库存联调（等 mingyi 回执）
      ```
    5. 无未读邮件且「任务现状」为空时，维持原有约定输出固定字符串「暂无未读消息」（入口脚本据此静默）
  - 任务管理 `task` 子命令组（操作本人 `workspaces/{.current_user}/tasks/` 下的任务包）：
    - 建任务 `uv run scripts/sync.py task create --name {任务名} [--from {协同单文件名}]`：
      1. 执行 `git pull`
      2. 校验任务名：非空、不含 `/`、不是 `.`/`..`，否则报错退出
      3. 创建 `tasks/{任务名}/` 目录并写入 `task.yaml`（status 初始为「未开始」；传了 --from 则记录上游协同单路径，统一归一化为 `inbox/{协同单文件名}` 前缀；不传则 from 写「无」）
      4. 同名目录已存在时报错退出（提示先 `task list` 看现状）
      5. 执行 `git add -> commit -> push`
    - 更新任务 `uv run scripts/sync.py task update --name {任务名} [--status {状态}] [--blocked {阻塞说明}]`：
      1. 执行 `git pull`；任务不存在时报错退出
      2. `--status` 与 `--blocked` 至少要给一个，都空则报错退出
      3. `--status` 只允许五态之一：`未开始 / 进行中 / 阻塞 / 待确认 / 已完成`，传其他值报错退出并列出合法值
      4. 更新 `task.yaml`：`--status` 写 status（非「阻塞」时 blocked_by 自动复位为「无」）；`--blocked` 写 blocked_by（阻塞时说明等什么）；`updated` 自动落当天日期
      5. 执行 `git add -> commit -> push`
    - 列任务 `uv run scripts/sync.py task list [--fmt json | markdown]`：列本人全部任务包及各自状态（markdown 表格列：任务/状态/阻塞原因/更新日期；json 为对象数组）
    - 任务包内 `task.yaml` 以外的文件（草稿、产出等）为自由文件，sync.py 不管


- **任务包（`workspaces/<user>/tasks/<任务名>/`）**
  - **任务从哪来**：通常是一张协同单——接到协同单（type: 协同单）后，接下来要做就建任务包并 `--from` 挂住原单；不接则直接 `write --type 退回 --ref <原单>`，**不要为退回的单建任务**。任务状态五态即产品语义：未开始（接了没动工）/ 进行中（正在做）/ 阻塞（卡住等别人，blocked_by 写等什么）/ 待确认（自认做完等对方确认）/ 已完成（对方确认收下，闭环）
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
  - `board/ledger/<user>.md`（通知台账）：由 CI 从各用户 inbox 的 frontmatter 派生，按时间倒序列出每封信的发件人、日期、type、subject、ref 链路。**只含元数据、不含信件正文，也不含已读状态**（已读在本地 `.sync_seen`，CI 无法也不该知道）
  - `board/task-board.md`（任务看板）：由 CI 聚合所有 `workspaces/*/tasks/*/task.yaml`，按五个状态分列，每行含任务名、owner、from 上游、blocked_by
  - 派生引擎：`workspaces/scripts/derive.py` 的 `render` 子命令（CI 与本地共用同一份代码，pytest 直接测它）：
    `uv run scripts/derive.py render --workspaces <workspaces目录> [--board-dir <输出board目录>] [--data-json <输出data.json路径>]`
    本地想预览派生效果时可用临时输出目录，产物不进 git
  - Markdown 版的读者是 clone 仓的人和 Agent；网页是另一份渲染产物（见「审计网页」），两者共用同一份聚合数据（data.json），口径永远一致
  - 派生文件的境地：改了也没用——下次 CI 重建会被覆盖；本地修改 board/ 属 lint 违规
  - 台账与看板是「读模型」：丢失可随时从 inbox + task.yaml 全量重建，无独立信息价值

- **审计网页（github.io 静态站点）**——本系统的对外主视图，数据与 Markdown 版同源
  - 产物三件套（由 `board.yml` 在 CI 内生成，经 `actions/upload-pages-artifact` + `actions/deploy-pages` 发布到 GitHub Pages，**不进 git 仓库**——仓库历史只留人写的东西，生成物活在 CI 产物与 Pages 托管层）：
    1. `data.json`：全量审计数据，键与 `site/app.js` 的读取契约严格一致——
       - `messages[]`：`{id, type, time, from, to, subject, ref?}`。`type` 取 frontmatter 的 type（缺失按「邮件」）；`time` 为 `MM-DD HH:mm` 展示格式；`to` 由 frontmatter 的列表拼接为逗号分隔字符串；`ref` 有才带
       - `tasks[]`：`{id, title, owner, state, updated_at, blocked_by?, ref?}`。`state` 是**英文五键**：`未开始→todo / 进行中→doing / 阻塞→blocked / 待确认→review / 已完成→done`（页面渲染层依赖，勿改）；`updated_at` 取 task.yaml 的 updated；阻塞任务带 `blocked_by`；有上游 from 的任务带 `ref`
       - **消息按文件名去重**：`sync.py write --to A,B` 会给 A、B 收件箱各写一份**同名文件**（同一封信的副本）；data.json 是「公文流水」，按文件名只留一份；而 `board/ledger/<user>.md` 按收件人分册保留每人收到的全部副本
       - **坏文件降级**：frontmatter 解析失败的信件不进 messages（无元数据可展示）；task.yaml 解析失败或 status 非五态时任务照常进 tasks、`state` 兜底为 `todo`——任何单个坏文件都不阻塞聚合构建（违规由 CI lint 标红）
    2. `site/index.html`：单页应用入口，自包含样式
    3. `site/app.js`：原生 JS，无框架（演示系统要能离线读源码）；fetch 一律用相对路径（站点挂在 `/message-board/` 子路径下，绝对路径会 404）；`data.json` 加载失败时回退内置 `MOCK_DATA`，本地双击 `site/index.html` 也能完整预览
  - 三个视图（底部浮动 Tab 切换，URL Hash 深链 `#view=stats|messages|kanban`）：
    - **全局概览**：信件流通总量、协同单闭环率、活跃协作任务、受阻事项四张统计卡，外加「任务五态分布」「协作活跃度排行（收发信件）」两组横向条形图——给演示的总览开场用
    - **消息审计**：全部信件元数据流水列表，可按公文类型（邮件/协同单/回执/退回）筛选，行内显示 ref 应答链引用
    - **任务看板**：五态分列的全员任务，阻塞项显示 blocked_by 依赖；每列在任务过多时列内独立滚动，列高占满当前视口
  - 视觉与交互规范（已在 `site/index.html` 原型落地，后续演进以此为准）：
    - 基调：Apple 式排版骨架（系统字体栈、大留白、圆角卡片、1px 半透明细线）+ **宣纸底色** `#f5f0e4`，卡片用亮半度的纸色 `#fdfbf5`，看板列用深一档纸色 `#efe8d8`
    - 点缀色取低饱和传统色：朱砂 `#b03a2e`（受阻/危险）、黛蓝 `#3a5a7b`（邮件/主强调）、松绿 `#4a7a5e`（已完成）、赭石 `#b07d2b`（阻塞/退回）、紫檀 `#7d5a78`（回执/ref 引用）、藤黄 `#c9a227`（待确认）、墨灰 `#8a8474`（未开始）
    - 布局：顶栏 = 品牌（Message Board · Audit View）+ 居中抬头「多人协作工作台 · Dashboard」+ 右侧动作区（数据快照时间 + GitHub 徽标链接，跳本仓库）；导航是底部居中的**浮动胶囊 Tab**（毛玻璃、吸底），激活态的黑色胶囊是同一个滑块、由 JS 量取按钮位置在三个视图间**穿梭滑动**；页面铺满视口高度；右下角有 44px 黛蓝「?」帮助 FAB（说明卡片含协作工作台与 Dashboard 介绍，从按钮上方弹出/收回带过渡动画，滚动条默认隐藏、悬停显现）；`prefers-reduced-motion` 下关闭全部动效
    - 数据：`data.json` 加载失败时回退到内置演示数据（`app.js` 的 `MOCK_DATA`），保证本地双击 `index.html` 也能完整预览交互
  - 页面只含元数据，不含信件正文；正文回仓库看
  - 前置手工步骤（仅一次）：仓库 Settings → Pages → Source 选 "GitHub Actions"，地址为 `https://<owner>.github.io/<repo>/`
  - 延迟预期：**push 后约 30~90 秒网页更新**（Actions 排队是大头）。审计系统看的是"发生过什么"，分钟级延迟可接受；秒级实时不是这个架构的目标，不要追

- **CI 治理（`.github/workflows/board.yml`）**——托管仓没有服务端 hook，用它顶替「邮局分拣中心」
  - 触发：push 到 main；防环条件 `if: github.actor != 'github-actions[bot]'`
  - 五个步骤：
    1. **聚合**：运行 `derive.py render`（扫所有 inbox frontmatter + 所有 task.yaml → 聚合数据 → `board/` Markdown + `_site/data.json`；渲染纯函数与 sync.py 共用 `parse_message`，且与 pytest 直测的是同一份代码）
    2. **渲染 Markdown**：聚合数据 → `board/ledger/<user>.md` + `board/task-board.md`
    3. **渲染网页产物**：聚合数据 → `data.json`；与 `site/index.html`、`site/app.js` 一起打成 Pages 产物（坏文件照常降级进数据、缺字段留空/兜底，不让单个坏文件阻塞构建）
    4. **lint**：`derive.py lint --base <before> --head <sha>`，发现违规即 workflow 失败标红，但不改任何文件：
       - 非 sync.py 提交记录中改动了 `workspaces/*/inbox/`（绕过投递引擎）——判定方式：改动过 inbox 文件的提交，其 commit message 不符合 sync.py 生成的固定模式 `docs: <user> sends a message to <...>`，即视为绕过（约定大于拦截的已知妥协）
       - `task.yaml` 的 status 不在五态枚举内（工作树全量扫描）
       - 非 board-bot 提交改动了 `board/`——判定方式：改动过 `board/` 的提交，其 commit message 不以 `[board-bot]` 前缀开头
    5. **发布**：Markdown 产物如有变化，以 board-bot 身份提交回仓库（commit message 前缀固定 `[board-bot]`，push 撞车 `git pull --rebase` 重试一次）；网页产物 `deploy-pages` 发布上线
  - 现实妥协（写进文档让人知情）：
    - 延迟：push 后约 30~90 秒台账/看板/网页才更新（Actions 排队），换来派生区绝对单写
    - lint 只能事后标红，做不到自建 git pre-receive 那种当场拦截；不强开 branch protection，以免「每写一封信都要等 CI 绿」

- **测试（`workspaces/tests/`）**——pytest，fixture 用临时目录 `git init` 的空仓当 origin
  - write 带 `--type`/`--ref` 的 frontmatter 正确性；`--ref` 文件不存在时的拒绝路径
  - task create / update / list 正常流；非法状态值拒绝；同名任务重复创建拒绝；非法任务名拒绝
  - check 的「任务现状」段输出；json `{messages, tasks}` 结构；全静默场景
  - 台账/看板/data.json 生成函数：喂伪造的 inbox + tasks，断言分簿、分列（时间倒序）、JSON schema、坏 frontmatter/坏 yaml 降级、data.json 同名副本去重（生成函数即 `derive.py`，由 sync.py 与 board.yml 共用同一份代码）
  - lint 规则：干净仓库无违规；绕过引擎写 inbox 被标；status 出五态被标；非 board-bot 改 board/ 被标

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
