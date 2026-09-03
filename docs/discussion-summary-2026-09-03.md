# 讨论纪要：message-board 协作审计能力升级（2026-09-03）

本文是对一轮设计讨论的归纳存档，记录"从对比两个协作 Demo 出发，到定下 message-board 升级方案"的完整结论。正式规范以 `docs/prd.md` 与 `docs/prd-detail.md` 为准；AGENT 行为约束见仓库根 `AGENTS.md`。

## 一、起点问题：仿真工作区是怎么工作的

讨论从 `05-仿真工作区`（成员机/机房/远端三视角的多人协作 Demo）切入。它的机制可以概括为：

- 每个协作者的本地只有**一个公共仓库的工作副本**，Agent 负责维护它与远端仓库的同步。
- 所谓"自动拉取、实时感应待办邮件"，本质是**约定动作**：每次与 Agent 交互／执行动作前先 `git pull`，新信件随 pull 进来后被脚本嗅到并提醒。没有真正的推送通道，实时性靠"高频交互 + 进门先拉"换取。

由此引出对比：`05-仿真工作区` 按业务方拆成多个仓（交易系统、频道页页面、早鸟票公共仓、plus 用增业务方），靠目录结构模拟"机房/远端/成员机"的部署关系；而 `message-board` 是**单仓邮局模型**——所有协作者共用一仓，`workspaces/<user>/inbox/` 是收件箱，`sync.py` 投递引擎收敛全部读写动作，git 历史即通信史，UserPromptSubmit hook 让 Agent 每轮对话自动"打卡查信"。

## 二、要补齐什么

结论：把 `05-仿真工作区` 体现的"企业协作"语义（派活、应答、追状态、可审计）补齐到 `message-board`，形成四项能力：

### 1. 公文类型 + ref 应答链

信分四种公文类型，写在 frontmatter 的 `type` 字段：

| 类型 | 用途 |
|---|---|
| 邮件（默认） | 同步情况、发通知，看一眼就过 |
| 协同单 | 正式派活给对方，需要应答 |
| 回执 | 接受协同单或完成后的应答 |
| 退回 | 不接这单并说明原因 |

回执/退回必须带 `--ref` 指向本人 inbox 里的原协同单文件，文件不存在则投递引擎直接拒发——保证"派出 → 应答"成对可查，应答链不断。

### 2. 五态任务包

"五态状态机"即任务状态的五个收敛枚举，全系统（引擎、看板、网页）共用，不许造第六个词：

| 状态 | 含义 |
|---|---|
| 未开始 | 接了单还没动工（建任务默认值） |
| 进行中 | 正在做 |
| 阻塞 | 卡住了，配合 `blocked_by` 写清"等什么" |
| 待确认 | 自认为做完，等对方确认 |
| 已完成 | 对方确认收下，闭环 |

任务以"任务包"形式挂在本人目录 `workspaces/<user>/tasks/<任务名>/` 下：`task.yaml` 是唯一状态地基（task / from / status / blocked_by / updated），包内其余文件（草稿、产出）自由编辑。状态变更必须经 `sync.py task create / update`，他人目录只读。`sync.py check` 追加「任务现状」段（进行中/阻塞计数 + 阻塞明细），让 Agent 每天打卡既呈新信、又提醒烂尾活。

### 3. CI 邮局治理 + 派生区 `board/`

托管仓没有服务端 hook，用 GitHub Actions（`.github/workflows/board.yml`）顶替"邮局分拣中心"，push 到 main 后自动跑五步：**聚合**（扫全部信头 + task.yaml，生成函数与 sync.py 共用同一份代码）→ **渲染 Markdown**（`board/ledger/<user>.md` 通知台账 + `board/task-board.md` 任务看板）→ **渲染网页产物**（`data.json` + `site/` 打包）→ **lint 质检**（绕过引擎写 inbox、status 出五态、非 board-bot 改 board/，一律标红但不动文件）→ **发布**（Markdown 派生区以 board-bot 身份提交回仓库，commit 前缀 `[board-bot]`；网页经 `upload-pages-artifact` + `deploy-pages` 上线）。

几条定死的权责与取舍：

- `board/` 是**读模型**，CI 唯一写手，客户端一律只读；丢失可随时从 inbox + task.yaml 全量重建。
- 防环：`if: github.actor != 'github-actions[bot]'`。
- **通知台账的用途**（讨论中专门问过）：把散落各收件箱的原始凭证聚合成"公文流转总账"——谁给谁投过信、什么类型、挂的哪张单、哪些协同单还没人应答、谁手头阻塞最多。它不是新信息，是给 PM/审计者一眼扫读的读视图。
- 现实妥协：lint 只能事后标红、不能当场拦截；不强开 branch protection，避免"每写一封信都等 CI 绿"。

### 4. 审计网页（github.io）

本系统的**对外主视图**，与 Markdown 台账共用同一份聚合数据，但只含元数据（谁发给谁、什么类型、什么状态），信件正文不离开仓库——github.io 托管的是脱敏产物。

- 形态：静态页面 + `data.json`，原生 JS 无框架；fetch 一律相对路径（站点挂在 `/message-board/` 子路径下）；`data.json` 加载失败回退内置 `MOCK_DATA`，本地双击也能完整预览。
- Actions 部署产物去向：CI 内生成 `data.json` 与 `site/index.html`、`site/app.js` 打成 Pages 产物（`upload-pages-artifact` → `deploy-pages`），**生成物不进 git**，仓库历史只留人写的东西；地址 `https://<owner>.github.io/message-board/`。前置手工步骤一次：Settings → Pages → Source 选 "GitHub Actions"。
- 实时性：push 后约 30~90 秒更新（Actions 排队是大头）。审计看的是"发生过什么"，分钟级延迟可接受，秒级实时不是目标。
- 三视图（底部浮动 Tab 切换，URL Hash 深链 `#view=stats|messages|kanban`）：
  - **全局概览**：信件流通总量、协同单闭环率、活跃任务、受阻事项四张统计卡 + 五态分布、活跃度排行条形图；
  - **消息审计**：全部公文元数据流水，可按类型筛选，行内显示 ref 应答链；
  - **任务看板**：全员任务五态分列，阻塞项标明被什么卡住，列内独立滚动。

### 网页视觉定稿（已在 site/ 原型落地）

- 基调：**Apple 式排版骨架**（系统字体栈、大留白、圆角卡片、1px 半透明细线）+ **宣纸底色** `#f5f0e4`；卡片 `#fdfbf5`、看板列 `#efe8d8`。
- 点缀色：低饱和传统色——朱砂 `#b03a2e`（受阻/危险）、黛蓝 `#3a5a7b`（邮件/主强调）、松绿 `#4a7a5e`（已完成）、赭石 `#b07d2b`（阻塞/退回）、紫檀 `#7d5a78`（回执/ref）、藤黄 `#c9a227`（待确认）、墨灰 `#8a8474`（未开始）。
- 布局：顶栏 = 品牌 + 居中抬头「**多人协作工作台 · Dashboard**」+ 数据快照时间；底部居中**浮动胶囊 Tab**（毛玻璃吸底）；页面铺满视口高度（footer 已移除）；看板列高占满视口、任务多时列内滚动；`prefers-reduced-motion` 下关闭动效。

## 三、产出与状态

| 事项 | 状态 | 位置 |
|---|---|---|
| 产品规范（含审计网页视觉规范） | 已写入 | `docs/prd.md` |
| 详细设计（四动作规范、CI 五步、派生区、测试清单、视觉规范） | 已写入 | `docs/prd-detail.md` |
| Agent 工作手册（铁则、公文类型、task 命令） | 已更新 | `AGENTS.md` |
| 审计网页交互原型（HTML+JS，MOCK 数据，截图验证通过） | 已完成 | `site/index.html`、`site/app.js` |
| 技术实施方案（TDD 任务拆解） | 待落盘 | `docs/superpowers/plans/2026-09-03-collab-audit-upgrade.md` |
| 引擎与 CI 开发 | 未开始 | `workspaces/scripts/`、`.github/workflows/board.yml` |

## 四、下一步

按既定拆解开发（pytest 临时 origin 夹具 → write `--type/--ref` → `derive.py` 聚合渲染 → `task` 子命令 → `check` 任务现状 → `board.yml` + lint → 本地端到端验证：pytest 全绿 + 真实仓库生成 `data.json` + 三视图截图核对），随后用 superpowers 的 subagent-driven-development 流程逐任务实施。
