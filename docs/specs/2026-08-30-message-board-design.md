# Message Board 设计文档

基于 Git 的 Agent-to-Agent 异步消息协作系统。

## 背景

多个 Agent（Claude Code / Codex）需要跨用户、跨项目传递消息。利用 Git 的分发能力：
- **发送方**：在对方目录写入消息文件，`git push` 到远程仓库
- **接收方**：Agent session 启动时 hook 自动 `git pull` + 检测新邮件，注入上下文提醒

## 协作流程

```
A 端（Alice）                   远程仓库                      B 端（Bob）
─────────────              ──────────────────              ─────────────
Agent 写信         ──push────>  messages/bob/alice-need-help.md
                                    │
                                    └────pull────>  sync.py --check 检测
                                                    到 messages/bob/ 有新文件
                                                    │
                                            Agent 提醒 Bob 有新邮件
```

**规则：**
- **收件人目录**：`messages/<recipient>/` — 发信方直接写入（而非自己的目录）
- **文件名**：`{YYYY-MM-DD}-{from}-{slug}.md`（全 ASCII，slug 由主题 kebab-case）
- **同步时机**：无定时任务，由 hook 触发（Agent 启动 session 时）
- **Git 冲突**：文件名含日期+发件人，同时冲突概率极低；`git pull --rebase` 兜底

## 目录结构

```
message-board/               # uv 管理的 Python 项目
├── docs/
│   └── specs/
│       └── 2026-08-30-message-board-design.md   # 本文档
├── messages/                # 消息目录（协作双方共享）
│   ├── alice/
│   └── bob/
├── sync.py                  # 同步引擎（发送 + 接收检测 + 初始化）
├── setup.sh                 # 一键安装脚本
├── tests/
│   ├── test_sync.py         # sync.py 单元测试
│   └── test_e2e.py          # 端到端冒烟测试（可选）
├── pyproject.toml           # uv 项目定义（requires-python, deps）
├── uv.lock                  # 依赖锁定
├── .python-version          # Python 版本锁（uv pin-project 自动生成）
├── .gitignore
└── README.md                # 使用说明
```

## sync.py 接口

**运行方式**：`uv run sync.py ...`（uv 管环境，以下命令在 message-board/ 目录内）

```bash
# 发送消息（直接传内容）
cd message-board
uv run sync.py --send \
  --to bob \
  --from alice \
  --subject "issue-42 修复说明" \
  --content "修复了 ..."

# 发送消息（从文件）
uv run sync.py --send \
  --to bob \
  --from alice \
  --subject "issue-42 修复说明" \
  --file ./fix-notes.md

# 接收检测（Agent hook 调用）
uv run sync.py --check --user alice
# 0 = 有新邮件（stdout 即提醒文本，注入 system-reminder）
# 1 = 无新邮件
```

### send 流程
1. **文件名**：`{YYYY-MM-DD}-{from}-{slug}.md`，slug 由 subject 前 5 词 kebab-case
2. **写入路径**：`messages/<to>/`
3. **frontmatter**：
```yaml
---
from: alice
to: bob
date: 2026-08-30T14:32:00+08:00
subject: "issue-42 修复说明"
---
```
4. **Git**：`git add messages/<to>/ && git commit -m "msg: <subject>" && git push`

### check 流程
1. 定位 `messages/<user>/` 目录
2. `git pull --rebase`
3. 读取上次 pull 的文件列表缓存 `.sync_seen`
4. 对比发现新文件：
   - 输出：`📬 New mail from alice: issue-42 修复说明`
   - Exit code 0（hook 检测到 0 后注入 system-reminder）
5. 无新文件：Exit code 1

## 双端 Agent 集成

### 1. Claude Code（SessionStart hook）

在协作项目根目录 `.claude/settings.json` 添加：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd /absolute/path/to/message-board && uv run sync.py --check --user alice"
          }
        ]
      }
    ]
  }
}
```

有邮件时 sync.py 输出注入 system-reminder → Agent 会话开始看到。

### 2. Codex（hooks.json）

项目层 `{project}/.codex/hooks.json`（Codex 加载 `features.hooks = true` 时生效）：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "type": "command",
        "command": "cd /absolute/path/to/message-board && uv run sync.py --check --user alice"
      }
    ]
  }
}
```

## setup.sh 一键安装

```bash
./setup.sh \
  --repo git@github.com:you/message-board.git \
  --name alice \
  --target-dir .
```

执行步骤：
1. `git clone <repo> <target-dir>/message-board`
2. `cd <target-dir>/message-board`
3. `uv init --name message-board --pin-project`（生成 pyproject.toml + .python-version + .gitignore）
4. `uv add pyyaml`（frontmatter 解析依赖）
5. `mkdir -p messages/<name>`
6. 将 `.sync_seen` 加入 `.gitignore`（本地状态文件，不进版本库）
7. 复制/合并 hook 配置到 `../.claude/settings.json` + `../.codex/hooks.json`（command 均为 `cd <abs>/message-board && uv run sync.py ...`）
8. 生成 `../AGENTS.md`（指引 Agent 自发使用：`uv run sync.py --check --user <name>`）
9. 初始化 git remote（`git remote add origin <repo>`）

## 技术选型

- **语言**：Python 3.9+（uv 管理）
- **运行时依赖**：PyYAML（frontmatter 解析）
- **消息格式**：Markdown + YAML frontmatter
- **Git**：命令行 `git add/commit/push/pull --rebase`（subprocess 调用）
- **Hook**：JSON 配置文件，Agent 原生支持
- **测试**：pytest（`uv add --dev pytest`）
- **包管理**：uv venv + lockfile（`uv.lock`）

## 注意事项

- **安全性**：仓库公开则消息内容泄漏，建议私有仓库 / 内网部署
- **权限模型**：默认可写任意收件人目录，后期可加白名单（`admins.txt`）
- **首次安装**：hook 需要项目级 trusted 状态，setup.sh 包含提醒文档
- **消息大小**：不建议传大文件，消息大于 10KB 告警

## 待验证 / 风险

- **Codex hook 事件名**：`SessionStart` 需要 Codex 源码确认（hooks.json schema）
- **多地同时安装**：同一 message-board 实例在多个用户机器的初始化流程
- **离线场景**：纯 git 即可，但考虑消息存在远程未同步的缓存机制
