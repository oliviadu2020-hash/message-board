# Message Board 设计文档 v2

基于 Git 的 Agent-to-Agent 异步消息协作系统——**以仓库为单位**的独立协作工作台。

## 核心模型

```
协作项目（message-board 仓库）
├── AGENTS.md                    # Agent 入口指引（含加入规则）
├── CLAUDE.md → AGENTS.md        # 软链接（Claude Code）
├── .claude/settings.json         # Claude SessionStart hook
├── .codex/hooks.json             # Codex SessionStart hook
│
├── scripts/
│   └── sync.py                   # CLI 工具：check（启动时）+ send（可选）
│
├── pyproject.toml
├── uv.lock
├── .python-version
├── tests/
│   └── test_sync.py
│
└── workspaces/                   # 协作工作区
    ├── alice/                    # 用户 alice 的私有工作区
    │   ├── inbox/                # alice 收件箱（他人通过 git 写入）
    │   ├── .sync_seen            # alice 已读邮件列表
    │   └── projects/             # alice 自己的文件（自由组织）
    ├── bob/
    │   ├── inbox/
    │   ├── .sync_seen
    │   └── reports/
    └── share/                    # 共享工作区（咖啡间）
        └── （自由文件）
```

**关键约定：**
- 只有本人可以写 `workspaces/<me>/`、`workspaces/<me>/inbox/` 以外的目录
- `workspaces/<me>/inbox/` 任何人可写（发件途径）
- `.sync_seen` 仅本人读写（状态文件）

## workspaces/<user>/ 内部结构约定

**发件方**：写入 `workspaces/<to>/inbox/<YYYY-MM-DD>-<from>-<slug>.md`（md 内容含 frontmatter）
**读件方**：自动检查 `workspaces/<me>/inbox/`，新文件 → 读取 + 提醒

### 写消息 = 唯一入口 sync.py --send
**严格禁止** Agent 手工 `git add/commit/push` 操作 message 文件——所有写入必须经由 sync.py 串行化管理。
Agent 唯一允许的操作：
```bash
cd message-board
uv run scripts/sync.py --send --to bob --from alice --subject "..." --content "..."
```
sync.py 内部流程：写入文件 → `git pull --rebase` → `git add` → `git commit` → `git push` → push 失败（他人已先提交）则 pull 重试。

### 读消息 = sync.py --check（hook 自动触发）
Agent 启动 session 时 hook 触发 `sync.py --check` → 检查 `workspaces/<me>/inbox/` 新文件 → 阅读 + 提醒。
check 是自动动作，发送是手动命令——Agent 不可以在没有 sync.py 时认为已发送。

## sync.py 接口

**运行方式**（项目根目录）：
```bash
uv run scripts/sync.py --send --to bob --from alice --subject "..." [--content "..." | --file ./x.md]
# 0 = 发送成功（写入 + git add/commit/push）
# 1 = 失败

uv run scripts/sync.py --check --user alice
# 0 = 有新邮件（推送提醒）
# 1 = 无邮件
# 2 = error
```

### send 流程
1. **文件名**： `{YYYY-MM-DD}-{from}-{slug}.md`（slug = subject 前 5 词 kebab-case）
2. **写入路径**： `workspaces/<to>/inbox/`
3. **frontmatter**： YAML (from/to/date/subject)
4. **git**： add + commit + push（发送完成，邮件已提交远程）

### check 流程
1. `git pull --rebase`（若有 remote origin，离线则跳过）
2. `workspaces/<user>/inbox/` 内新文件 → 提醒 + 记录 `.sync_seen`
3. `workspaces/<user>/.sync_seen` 只读自己（防止脏读）

## 加入流程（新人）

Agent A 已使用，B 想加入：

1. B 克隆仓库
2. B 运行：`./scripts/setup.sh --name bob`（或手动新增配置）
   - 自动创建 `workspaces/bob/inbox/`
   - 合并 hook 配置到 `.claude/settings.json` + `.codex/hooks.json`
3. B 启动 Agent → 自动使能

## AGENTS.md 规则（模板内容）

```markdown
# Message Board Collaboration Guide

## Rules

- Write messages ONLY via `sync.py --send` (personal workspace protection).
- Never manually edit files in `workspaces/<u>/inbox/`.
- Your own `workspaces/<me>/` (outside inbox) is private; others must not modify.
- `workspaces/share/` is free-for-all.
- Messages are Markdown with YAML frontmatter.

## Send a Message

\`\`\`bash
cd message-board
uv run scripts/sync.py --send --to <user> --from <me> --subject "..." --content "..."
\`\`\`

## Join This Collaboration

\`\`\`bash
./scripts/setup.sh --name <yourname>
uv sync
\`\`\`

Then add your name to workspaces/.
```

## 目录结构（模板）

```
message-board/
├── docs/
│   └── specs/
├── workspaces/
│   ├── alice/
│   │   ├── inbox/
│   │   ├ .sync_seen
│   │   └ projects/
│   └── share/
├── scripts/
│ └ sync.py
├── tests/
│   └── test_sync.py
├── AGENTS.md
├── CLAUDE.md -> AGENTS.md
├── .claude/settings.json
├── .codex/hooks.json
├── pyproject.toml
├── uv.lock
├── .gitignore
├── .python-version
└── README.md
```

## 技术选型

- **语言**：Python 3.9+（uv）
- **运行时依赖**：PyYAML
- **通讯**：Git commit/push CLI；无网络库刚性依赖
- **Hook**：`.claude/settings.json` SessionStart / `.codex/hooks.json` SessionStart

## 安全性

- workspaces/ 的主权式：个人主权（私有），inbox 共享（弱势但公信）
- 公开仓库则所有消息泄漏；建议私有仓或内网部署
- sync.py 对待 `.sync_seen` 仅为本人

## 与前一版本的关系

v1（已有实现）侧重「做实验」：仅分 messages/alice|bob/ 简单目录，验证可行性。
v2（本设计）是「成熟产品」：完整的工作区 + 主权 + 保持无 hook 资源监听、加入自由。

**升级路径**：v2 代码完全重写（不同目录结构），旧测试可适配但建议重新构建测试。