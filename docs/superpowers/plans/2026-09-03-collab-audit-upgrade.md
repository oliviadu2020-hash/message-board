# Message Board 协作审计能力升级 实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `05-仿真工作区` 体现的企业协作语义（公文类型 + ref 应答链、五态任务包、CI 邮局治理 + `board/` 派生区、审计网页数据源）补齐到 message-board，并全部通过 pytest 与一次本地端到端验证。

**Architecture:** 在既有单仓邮局模型上增量扩展：`sync.py` 增加 `write --type/--ref`、`task create/update/list` 子命令、`check` 的「任务现状」段；新增 `workspaces/scripts/derive.py` 作为**聚合渲染引擎**（扫描 inbox frontmatter + task.yaml → `board/ledger/<user>.md`、`board/task-board.md`、`data.json`），由 CI 与本地共用同一份代码；新增 `.github/workflows/board.yml` 做 CI 五步（聚合→渲染 Markdown→渲染 data.json→lint→发布）。网页前端 `site/` 已定稿，本计划不修改其视觉，只对齐 `data.json` 契约。

**Tech Stack:** Python 3.12（`workspaces/` 内 uv 工程，PyYAML），pytest 8，原生 git 命令（无第三方），GitHub Actions（board.yml），原生 JS 静态页（已存在）。

**Spec:** `docs/prd.md`（设计协议）、`docs/prd-detail.md`（详细设计）、`docs/discussion-summary-2026-09-03.md`（讨论纪要）。计划从 Spec 论证；执行者同时读 Spec 与本计划。与 Spec 冲突时以 `docs/prd.md` 为准。

## Global Constraints

以下约束对每个任务生效（原文或规范值照抄自 Spec）：

- 工作区命令统一先 `cd <project>/workspaces`，再 `uv run scripts/...`；测试统一 `uv run pytest`。
- 公文 `type` 枚举只有四个值：`邮件 / 协同单 / 回执 / 退回`；`--type` 不传默认 `邮件`，且 frontmatter 恒写 `type` 字段。
- `--type 回执/退回` 必须同时传 `--ref <原单文件名>`，且 `--ref` 指向的文件必须存在于**本人** inbox，否则报错退出、不发信（不产生任何新文件/新提交）。
- 任务状态枚举只有五态：`未开始 / 进行中 / 阻塞 / 待确认 / 已完成`；全系统（引擎、task.yaml、聚合、lint）不许出现第六个词。`task.yaml` 的 `blocked_by` 非阻塞态默认「无」。
- `task.yaml` schema：`task / from / status / blocked_by / updated` 五个字段；`from` 无上游时写「无」，有上游写 `inbox/<协同单文件名>`；`updated` 为 `YYYY-MM-DD` 当天日期。
- `board/` 是派生区：CI 唯一写手，客户端只读；本计划所有本地执行（含端到端验证）**不得把生成的 `board/`、`data.json` 提交进 git**，验证后清理。
- 坏文件降级规则：yaml 解析失败的信件/任务**照常进聚合数据、缺字段留空**，绝不让单个坏文件阻塞聚合构建。
- 写信即公开发言；测试一律使用 pytest 临时 `git init` 仓库当 origin，**严禁触碰真实 inbox**（本机 `workspaces/.current_user` 缺失，任何真实 `sync.py write/check` 都不执行）。
- `data.json` 与 `site/` 前端契约（app.js 已定死）：`messages[].type` 为中文四值；`tasks[].state` 为英文五键映射 `未开始→todo, 进行中→doing, 阻塞→blocked, 待确认→review, 已完成→done`；`time/updated_at` 为展示字符串；`ref/blocked_by` 缺省省略。
- 派生区 Markdown 由 board-bot 提交，commit message 前缀固定 `[board-bot]`；CI 防环 `if: github.actor != 'github-actions[bot]'`。
- 本仓库 git 历史即通信史：每个任务结尾做一次原子 commit，commit message 用现有风格（`feat:` / `test:` / `chore:` 前缀）。

---

## 文件结构

本次要创建/修改的文件及其职责（分解决策在此锁定）：

| 文件 | 状态 | 职责 |
|---|---|---|
| `workspaces/pyproject.toml` | 修改 | 加 pytest dev 依赖组 + pytest 配置（`pythonpath` 指向 `scripts`，`testpaths` 指向 `tests`） |
| `workspaces/tests/conftest.py` | 创建 | 共享 fixture：临时 bare origin + 工作副本 + `.current_user=alice` + monkeypatch 模块路径 |
| `workspaces/tests/test_write.py` | 创建 | `write --type/--ref` 行为与拒绝路径 |
| `workspaces/tests/test_task.py` | 创建 | `task create/update/list` 正常流与非法路径 |
| `workspaces/tests/test_check.py` | 创建 | `check` 的「任务现状」段、json 结构、全静默场景 |
| `workspaces/tests/test_derive.py` | 创建 | 聚合/台账/看板/data.json 生成函数 + 坏文件降级 |
| `workspaces/tests/test_lint.py` | 创建 | `derive.py lint` 三条违规检测 |
| `workspaces/scripts/sync.py` | 修改 | `write` 支持 type/ref；新增 `task` 子命令组；`check` 追加任务现状段 |
| `workspaces/scripts/derive.py` | 创建 | 聚合渲染引擎 + lint 子命令（与 sync.py、board.yml 共用） |
| `.github/workflows/board.yml` | 创建 | CI 五步：聚合渲染 → data.json → lint → board-bot 回提 → Pages 发布 |
| `.gitignore` | 修改 | 追加本地生成的 `data.json`、`_site/`（生成物不进 git） |

依赖关系：Task 1（夹具）→ Task 2/3/4（sync.py 功能，各自 TDD）→ Task 5（check 依赖 task 目录）→ Task 6（derive 纯函数）→ Task 7（lint 依赖夹具 git 历史）→ Task 8（board.yml）→ Task 9（端到端验证）。site/ 前端已完成且不修改。

---

## Task 0: 提交现有未落盘的设计产物（基线提交）

**背景**：工作树里有未提交的升级设计（`AGENTS.md`、`docs/prd.md`、`docs/prd-detail.md` 改动 + `docs/discussion-summary-2026-09-03.md`、`site/` 未跟踪），git 历史还停在旧版。先落盘，让后续功能提交历史干净。这些文件**不是** inbox 文件，可用直接 git 操作；但按铁则第 1 条不得对 `workspaces/*/inbox/` 做直接 git 操作——本任务不触碰 inbox。

**Files:**
- Commit: `AGENTS.md`, `docs/prd.md`, `docs/prd-detail.md`, `docs/discussion-summary-2026-09-03.md`, `site/index.html`, `site/app.js`, `docs/guides/discuss-message-board-prd.md`（已在历史中则跳过）

- [ ] **Step 1: 检查当前状态**

Run: `git status --short`
Expected: 看到 ` M AGENTS.md`、` M docs/prd.md`、` M docs/prd-detail.md`、`?? docs/discussion-summary-2026-09-03.md`、`?? site/` 等。若工作树已干净（设计早已提交），直接跳过本任务。

- [ ] **Step 2: 提交设计文档**

```bash
git add AGENTS.md docs/prd.md docs/prd-detail.md docs/discussion-summary-2026-09-03.md
git commit -m "docs: 定稿协作审计升级 PRD 与讨论纪要"
```

- [ ] **Step 3: 提交网页原型**

```bash
git add site/
git commit -m "feat: 审计网页三视图原型（site/index.html + app.js，MOCK 数据可离线预览）"
```

- [ ] **Step 4: 验证基线**

Run: `git status --short`
Expected: 只剩本仓库中已存在的旧改动或无输出（即干净）。注意 `workspaces/.current_user` 缺失属正常（gitignored），不要补写。

---

## Task 1: pytest 基建 + 临时 origin 夹具

**Files:**
- Modify: `workspaces/pyproject.toml`
- Create: `workspaces/tests/conftest.py`
- Test: `workspaces/tests/test_write.py`（冒烟：夹具能跑通真实 write 流程）

**Interfaces:**
- Produces: fixture `repo(tmp_path, monkeypatch) -> Path`（返回工作副本根 `work/`；已把 `sync.WORKSPACES_DIR`/`sync.REPO_ROOT` 与 `derive.WORKSPACES`/`derive.REPO_ROOT` monkeypatch 到临时仓库）。所有后续测试依赖它。

- [ ] **Step 1: pyproject 增加 pytest 配置**

把 `workspaces/pyproject.toml` 改为：

```toml
[project]
name = "message-board-workspaces"
version = "0.1.0"
description = "Message Board workspaces CLI (sync.py): read/write/check multi-user messages via git"
requires-python = ">=3.11"
dependencies = [
    "PyYAML>=6.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["scripts"]

[tool.uv]
package = false
```

- [ ] **Step 2: 同步 uv 环境**

Run: `uv sync`
Expected: 成功安装 pytest（无报错）。若提示 lockfile 更新，运行 `uv lock` 后再次 `uv sync`。

- [ ] **Step 3: 写共享夹具（先写文件，稍后由冒烟测试驱动验证）**

创建 `workspaces/tests/conftest.py`：

```python
"""共享 fixture：临时 bare origin + 工作副本，隔离一切 git 副作用。"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))


def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """搭出 alice 视角的隔离仓库：
    - tmp/origin.git（bare）为 origin
    - tmp/work 为工作副本，workspaces/{alice,bob} 各含 inbox/workspace/log.md
    - .current_user=alice，初始提交已 push 到 origin/main
    - monkeypatch sync.py 的路径常量指向临时仓库

    derive.py 的路径 patch 由 Task 6 追加的 derive_repo fixture 提供
    （derive 模块在本 task 尚未创建，不能在 conftest 顶层 import）。
    """
    import sync  # noqa: F401  (先确保可导入)

    origin = tmp_path / "origin.git"
    work = tmp_path / "work"

    git("init", "-b", "main", "--bare", str(origin), cwd=tmp_path)
    git("clone", str(origin), str(work), cwd=tmp_path)

    ws = work / "workspaces"
    for u in ("alice", "bob"):
        (ws / u / "inbox").mkdir(parents=True)
        (ws / u / "workspace").mkdir(parents=True)
        (ws / u / "log.md").write_text(f"# {u} 的工作日志\n", encoding="utf-8")
    (ws / ".current_user").write_text("alice", encoding="utf-8")
    (work / ".gitignore").write_text(
        "workspaces/.current_user\nworkspaces/*/.sync_seen\n.venv/\n__pycache__/\n",
        encoding="utf-8",
    )
    git("config", "user.name", "tester", cwd=work)
    git("config", "user.email", "tester@example.com", cwd=work)
    git("config", "commit.gpgsign", "false", cwd=work)
    git("add", "-A", cwd=work)
    git("commit", "-m", "init", cwd=work)
    git("push", "-u", "origin", "HEAD", cwd=work)

    monkeypatch.setattr(sync, "WORKSPACES_DIR", ws)
    monkeypatch.setattr(sync, "REPO_ROOT", work)
    return work
```

- [ ] **Step 4: 写冒烟测试（驱动夹具可用）**

创建 `workspaces/tests/test_write.py`：

```python
"""write 子命令冒烟 + type/ref 行为。"""
from argparse import Namespace

import pytest
import sync


def inbox_files(repo, user):
    return sorted((repo / "workspaces" / user / "inbox").glob("*.md"))


def run_write(repo, monkeypatch, *, to, subject, content, mtype="邮件", ref=None):
    """以当前用户(夹具为 alice)执行一次 sync write，返回生成的收件箱文件路径。"""
    cmd = Namespace(to=to, subject=subject, content=content, file=None,
                    type=mtype, ref=ref)
    sync.cmd_write(cmd)  # 内部执行 git pull / commit / push
    files = inbox_files(repo, to)
    assert len(files) == 1, "write 应恰好生成一封新邮件"
    return files[0]


def test_write_smoke(repo):
    f = run_write(repo, monkeypatch=None, to="bob", subject="排期",
                  content="明早评审改到下午")
    text = f.read_text(encoding="utf-8")
    # 冒烟只锁升级前后不变的事实: 信件文件生成、subject 写入、收件人正确
    assert f.name.endswith("-alice.md")
    assert "subject: 排期" in text
    assert "- bob" in text
```

> 说明：`run_write` 的 `monkeypatch` 参数仅为占位，使调用方不必传；真实断言不依赖 capsys。冒烟刻意不锁 `type` 字段（该字段在 Task 2 才引入，避免跨 Task 红绿翻转）；type 行为由 Task 2 的失败测试驱动。

- [ ] **Step 5: 跑冒烟测试**

Run: `uv run pytest tests/test_write.py -v`
Expected: 1 passed（夹具 init→write→commit→push 全链路在临时仓库里跑通）。

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock tests/conftest.py tests/test_write.py
git commit -m "test: pytest 基建与临时 origin 夹具（write 冒烟通过）"
```

---

## Task 2: write 支持 --type / --ref

**Files:**
- Modify: `workspaces/scripts/sync.py`（`build_message`、`cmd_write`、`main` 的 argparse）
- Test: `workspaces/tests/test_write.py`

**Interfaces:**
- Consumes: Task 1 的 `repo` fixture。
- Produces: `sync.build_message(from_user, to_list, subject, body, mtype="邮件", ref=None) -> str`；`cmd_write` 读取 `Namespace.to/subject/content/file/type/ref`。后续任务（回执链路、derive 渲染）依赖 frontmatter 的 `type`/`ref` 字段。

- [ ] **Step 1: 写失败测试（追加到 test_write.py）**

```python
def test_write_default_type_email(repo):
    f = run_write(repo, monkeypatch=None, to="bob", subject="排期",
                  content="明早评审改到下午")
    text = f.read_text(encoding="utf-8")
    assert "type: 邮件" in text
    assert "subject: 排期" in text


def test_write_xiedan_sets_type(repo):
    f = run_write(repo, monkeypatch=None, to="bob", subject="派活",
                  content="请完成对账", mtype="协同单")
    text = f.read_text(encoding="utf-8")
    assert "type: 协同单" in text


def _seed_xiedan_to_alice(repo):
    """让 bob 给 alice 投一张协同单（真实走引擎），返回其在 alice inbox 的文件名。"""
    # 切身份为 bob
    (repo / "workspaces" / ".current_user").write_text("bob", encoding="utf-8")
    cmd = Namespace(to="alice", subject="申请核对交易数据", content="请联调",
                    file=None, type="协同单", ref=None)
    sync.cmd_write(cmd)
    # 切回 alice
    (repo / "workspaces" / ".current_user").write_text("alice", encoding="utf-8")
    files = inbox_files(repo, "alice")
    assert len(files) == 1
    return files[0].name


def test_write_receipt_without_ref_rejected(repo):
    before = inbox_files(repo, "bob")
    with pytest.raises(SystemExit):
        run_write(repo, monkeypatch=None, to="bob", subject="回执",
                  content="我接了", mtype="回执", ref=None)
    assert inbox_files(repo, "bob") == before, "拒发时不得产生任何新文件"


def test_write_receipt_ref_missing_rejected(repo):
    before = inbox_files(repo, "bob")
    with pytest.raises(SystemExit):
        run_write(repo, monkeypatch=None, to="bob", subject="回执",
                  content="我接了", mtype="回执", ref="不存在.md")
    assert inbox_files(repo, "bob") == before


def test_write_receipt_with_ref_ok(repo):
    origin_name = _seed_xiedan_to_alice(repo)
    f = run_write(repo, monkeypatch=None, to="bob", subject="回执",
                  content="已接受", mtype="回执", ref=origin_name)
    text = f.read_text(encoding="utf-8")
    assert f"type: 回执" in text
    assert f"ref: {origin_name}" in text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_write.py -v`
Expected: 既有 1 个冒烟通过；新 5 个 FAIL（无 `type`/`ref` 字段、`SystemExit` 未触发）。

- [ ] **Step 3: 修改 build_message**

把现有 `build_message`（第 125–135 行附近）整体替换为：

```python
def build_message(from_user: str, to_list: list[str], subject: str, body: str,
                  mtype: str = "邮件", ref: str | None = None) -> str:
    now = datetime.now(timezone.utc).astimezone()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S %z")
    fm = {
        "from": from_user,
        "to": to_list,
        "date": date_str,
        "subject": subject,
        "type": mtype,
    }
    if ref:
        fm["ref"] = ref
    fm_text = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    return f"{FRONTMATTER_SEP}\n{fm_text}{FRONTMATTER_SEP}\n{body.rstrip()}\n"
```

- [ ] **Step 4: 修改 cmd_write 校验与调用**

在 `cmd_write` 中，`subject` 校验之后、`git_pull()` 之前插入校验块，并把消息构建改为传参：

```python
    # --- 公文类型与应答链校验 ---
    mtype = args.type or "邮件"
    if mtype not in ("邮件", "协同单", "回执", "退回"):
        die(f"--type 非法: {mtype},合法值为 邮件/协同单/回执/退回")
    if mtype in ("回执", "退回"):
        if not args.ref:
            die(f"--type {mtype} 必须同时传 --ref 指向原协同单文件名")
        origin = WORKSPACES_DIR / from_user / "inbox" / args.ref
        if not origin.exists():
            die(f"--ref 指向的协同单不存在: {args.ref}")
```

并把：

```python
    message = build_message(from_user, to_list, subject, body)
```

替换为：

```python
    message = build_message(from_user, to_list, subject, body, mtype=mtype, ref=args.ref)
```

- [ ] **Step 5: argparse 增加参数**

在 `main()` 中 `p_write` 定义处追加：

```python
    p_write.add_argument("--type", choices=["邮件", "协同单", "回执", "退回"],
                         default="邮件", help="公文类型: 邮件/协同单/回执/退回")
    p_write.add_argument("--ref", help="应答原协同单文件名(回执/退回必填)")
```

- [ ] **Step 6: 跑测试确认通过**

Run: `uv run pytest tests/test_write.py -v`
Expected: 5 passed。

- [ ] **Step 7: Commit**

```bash
git add scripts/sync.py tests/test_write.py
git commit -m "feat: sync.py write 支持公文类型 type/ref 应答链校验"
```

---

## Task 3: sync.py task 子命令（create / update / list）

**Files:**
- Modify: `workspaces/scripts/sync.py`（新增任务常量、task.yaml 读写助手、三个子命令、argparse）
- Test: `workspaces/tests/test_task.py`

**Interfaces:**
- Produces（后续 derive/check 依赖）:
  - `TASK_STATUSES = ["未开始", "进行中", "阻塞", "待确认", "已完成"]`
  - `tasks_dir(user) -> Path`（`workspaces/<user>/tasks`）
  - `task_yaml_path(user, name) -> Path`（`tasks/<name>/task.yaml`）
  - `load_task_yaml(user, name) -> dict`（yaml 解析失败返回 `{}`，不抛）
  - `cmd_task_create(args)`：读 `Namespace.name / from`
  - `cmd_task_update(args)`：读 `Namespace.name / status / blocked`
  - `cmd_task_list(args)`：读 `Namespace.fmt`
- `task.yaml` 磁盘 schema（yaml.safe_dump，`allow_unicode=True, sort_keys=False`，字段顺序固定）：
  ```yaml
  task: <任务名>          # = 目录名
  from: inbox/<协同单文件名>  # 无上游写「无」
  status: 未开始            # 五态之一
  blocked_by: 无           # status=阻塞 时写等什么
  updated: 2026-09-03      # 当天日期，自动落
  ```

- [ ] **Step 1: 写失败测试**

创建 `workspaces/tests/test_task.py`：

```python
"""task 子命令组：create / update / list。"""
from argparse import Namespace
from datetime import datetime

import pytest
import sync
import yaml


def task_yaml(repo, user, name):
    return repo / "workspaces" / user / "tasks" / name / "task.yaml"


def run_create(repo, name, upstream=None):
    cmd = Namespace(name=name, from_file=upstream)
    sync.cmd_task_create(cmd)
    return task_yaml(repo, "alice", name)


def test_task_create_defaults(repo):
    f = run_create(repo, "下单锁库存联调")
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    assert data["task"] == "下单锁库存联调"
    assert data["status"] == "未开始"
    assert data["blocked_by"] == "无"
    assert data["from"] == "无"
    assert data["updated"] == datetime.now().strftime("%Y-%m-%d")


def test_task_create_with_from(repo):
    f = run_create(repo, "对账联调", upstream="2026-09-03-10-00-00-+0800-bob.md")
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    assert data["from"] == "inbox/2026-09-03-10-00-00-+0800-bob.md"


def test_task_create_dup_rejected(repo):
    run_create(repo, "重名任务")
    before = sorted((repo / "workspaces" / "alice" / "tasks").glob("*/task.yaml"))
    with pytest.raises(SystemExit):
        run_create(repo, "重名任务")
    after = sorted((repo / "workspaces" / "alice" / "tasks").glob("*/task.yaml"))
    assert before == after, "重复创建不得产生第二个任务包"


def test_task_create_bad_name_rejected(repo):
    with pytest.raises(SystemExit):
        run_create(repo, "a/b")
    assert not (repo / "workspaces" / "alice" / "tasks" / "a" / "b").exists()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_task.py -v`
Expected: 4 FAIL（`AttributeError: sync.cmd_task_create`）。

- [ ] **Step 3: 新增任务常量与读写助手**

在 `sync.py` 的「任务包」区域（`# ---------- 任务管理 ----------`）写入：

```python
# ---------- 任务管理 ----------

TASK_STATUSES = ["未开始", "进行中", "阻塞", "待确认", "已完成"]


def today_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def tasks_dir(user: str) -> Path:
    return WORKSPACES_DIR / user / "tasks"


def task_yaml_path(user: str, name: str) -> Path:
    return tasks_dir(user) / name / "task.yaml"


def load_task_yaml(user: str, name: str) -> dict:
    f = task_yaml_path(user, name)
    if not f.exists():
        die(f"任务不存在: {name}（先 task create 或 task list 看现状）")
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def save_task_yaml(user: str, name: str, data: dict) -> Path:
    f = task_yaml_path(user, name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return f
```

- [ ] **Step 4: 实现三个子命令**

在 `save_task_yaml` 之后写入：

```python
def cmd_task_create(args: argparse.Namespace) -> None:
    user = read_current_user()
    name = args.name.strip()
    if not name or "/" in name or name in (".", ".."):
        die("非法任务名: 不能为空、含 / 或为 . / ..")
    git_pull()
    target = task_yaml_path(user, name)
    if target.exists():
        die(f"同名任务已存在: {name}（先 task list 看现状）")
    data = {
        "task": name,
        "from": f"inbox/{args.from_file}" if args.from_file else "无",
        "status": "未开始",
        "blocked_by": "无",
        "updated": today_str(),
    }
    saved = save_task_yaml(user, name, data)
    git_add_commit_push([saved], f"docs: {user} 创建任务 {name}")


def cmd_task_update(args: argparse.Namespace) -> None:
    user = read_current_user()
    name = args.name.strip()
    if not name or "/" in name:
        die("非法任务名")
    git_pull()
    data = load_task_yaml(user, name)
    if args.status:
        if args.status not in TASK_STATUSES:
            die(f"--status 只允许五态之一: {' / '.join(TASK_STATUSES)}")
        data["status"] = args.status
        if args.status != "阻塞":
            data["blocked_by"] = "无"
    if args.blocked:
        data["blocked_by"] = args.blocked
    if args.status is None and args.blocked is None:
        die("task update 至少需要 --status 或 --blocked 之一")
    data["updated"] = today_str()
    saved = save_task_yaml(user, name, data)
    git_add_commit_push([saved], f"docs: {user} 更新任务 {name}")


def cmd_task_list(args: argparse.Namespace) -> None:
    user = read_current_user()
    git_pull()
    rows = []
    root = tasks_dir(user)
    if root.exists():
        for p in sorted(root.glob("*/task.yaml")):
            data = load_task_yaml(user, p.parent.name)
            rows.append({
                "task": data.get("task") or p.parent.name,
                "status": data.get("status") or "?",
                "blocked_by": data.get("blocked_by") or "无",
                "updated": data.get("updated") or "?",
            })
    if args.fmt == "json":
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print("|任务|状态|阻塞原因|更新日期|")
    print("|----|----|--------|--------|")
    for r in rows:
        print(f"|{r['task']}|{r['status']}|{r['blocked_by']}|{r['updated']}|")
```

- [ ] **Step 5: argparse 挂载 task 子命令组**

在 `main()` 中追加（`p_check` 定义之后）：

```python
    p_task = sub.add_parser("task", help="任务包管理")
    task_sub = p_task.add_subparsers(dest="task_cmd", required=True)

    p_create = task_sub.add_parser("create", help="创建任务包")
    p_create.add_argument("--name", required=True, help="任务名(即目录名)")
    p_create.add_argument("--from", dest="from_file", help="上游协同单文件名")

    p_update = task_sub.add_parser("update", help="更新任务状态")
    p_update.add_argument("--name", required=True, help="任务名")
    p_update.add_argument("--status", choices=TASK_STATUSES, help="五态之一")
    p_update.add_argument("--blocked", help="阻塞说明(等什么)")

    p_list = task_sub.add_parser("list", help="列出本人任务")
    p_list.add_argument("--fmt", choices=["markdown", "json"], default="markdown")
```

并在 `main()` 的 dispatch 处追加分支：

```python
    elif args.cmd == "task":
        if args.task_cmd == "create":
            cmd_task_create(args)
        elif args.task_cmd == "update":
            cmd_task_update(args)
        elif args.task_cmd == "list":
            cmd_task_list(args)
```

> 注意：`main()` 里 `args` 是命名空间，`args.task_cmd` 仅当 `cmd=task` 时存在——argparse subparsers 不会污染其他分支。

- [ ] **Step 6: 跑测试确认通过**

Run: `uv run pytest tests/test_task.py -v`
Expected: 4 passed。

- [ ] **Step 7: Commit**

```bash
git add scripts/sync.py tests/test_task.py
git commit -m "feat: sync.py task 子命令组（create/update/list + 五态收敛）"
```

---

## Task 4: check 追加「任务现状」段

**Files:**
- Modify: `workspaces/scripts/sync.py`（`cmd_check`）
- Test: `workspaces/tests/test_check.py`

**Interfaces:**
- Consumes: Task 3 的 `tasks_dir` / `task_yaml_path` / `load_task_yaml`、Task 2 的 type/ref 写信。
- Produces: `check` 的 markdown 输出在信件表后追加任务现状段；json 输出由「裸数组」升级为 `{messages: [...], tasks: {...}}`。

- [ ] **Step 1: 写失败测试**

创建 `workspaces/tests/test_check.py`：

```python
"""check 命令：任务现状段、json 结构、全静默场景。"""
import json
from argparse import Namespace

import pytest
import sync


def run_create(repo, name):
    sync.cmd_task_create(Namespace(name=name, from_file=None))


def run_update(repo, name, status=None, blocked=None):
    sync.cmd_task_update(Namespace(name=name, status=status, blocked=blocked))


def run_check(repo, capsys, fmt="markdown"):
    sync.cmd_check(Namespace(fmt=fmt))
    return capsys.readouterr().out


def test_check_no_unread_no_tasks_silent(repo, capsys):
    out = run_check(repo, capsys)
    assert out.strip() == "暂无未读消息"


def test_check_marks_task_section_markdown(repo, capsys):
    run_create(repo, "下单锁库存联调")
    run_update(repo, "下单锁库存联调", status="阻塞", blocked="等 bob 回执")
    out = run_check(repo, capsys)
    assert "## 任务现状" in out
    assert "进行中 0 件 / 阻塞 1 件" in out
    assert "下单锁库存联调" in out
    assert "等 bob 回执" in out


def test_check_task_section_json(repo, capsys):
    run_create(repo, "任务甲")
    run_update(repo, "任务甲", status="进行中")
    out = run_check(repo, capsys, fmt="json")
    payload = json.loads(out)
    assert set(payload) == {"messages", "tasks"}
    assert payload["tasks"]["in_progress"] == ["任务甲"]
    assert payload["tasks"]["blocked"] == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_check.py -v`
Expected: 第 2、3 个 FAIL（尚无任务现状段）；第 1 个 PASS（既有行为）。

- [ ] **Step 3: 新增任务现状统计助手**

在 `sync.py` 中 `cmd_task_list` 之后写入：

```python
def task_status_summary(user: str) -> dict:
    """统计本人任务: 进行中清单 + 阻塞明细。"""
    in_progress: list[str] = []
    blocked: list[dict] = []
    root = tasks_dir(user)
    if not root.exists():
        return {"in_progress": in_progress, "blocked": blocked}
    for p in sorted(root.glob("*/task.yaml")):
        data = load_task_yaml(user, p.parent.name)
        status = data.get("status")
        name = data.get("task") or p.parent.name
        if status == "进行中":
            in_progress.append(name)
        elif status == "阻塞":
            blocked.append({"name": name, "blocked_by": data.get("blocked_by") or "无"})
    return {"in_progress": in_progress, "blocked": blocked}
```

- [ ] **Step 4: 重写 cmd_check**

把现有 `cmd_check`（第 233–269 行附近）整体替换为：

```python
def cmd_check(args: argparse.Namespace) -> None:
    user = read_current_user()
    git_pull()
    seen = load_seen(user)

    unread: list[dict] = []
    for p in list_inbox(user):
        if p.name in seen:
            continue
        msg = parse_message(p.read_text(encoding="utf-8"))
        if "raw" in msg:
            unread.append({"from": "?", "to": [], "date": "?", "subject": f"[无法解析] {p.name}"})
        else:
            to_val = msg.get("to", [])
            if not isinstance(to_val, list):
                to_val = [to_val]
            unread.append({
                "from": str(msg.get("from", "?")),
                "to": [str(t) for t in to_val],
                "date": str(msg.get("date", "?")),
                "subject": str(msg.get("subject", "")),
                "type": str(msg.get("type", "邮件")),
                "ref": str(msg.get("ref", "")) or None,
            })

    tasks = task_status_summary(user)
    has_task_section = bool(tasks["in_progress"] or tasks["blocked"])

    if args.fmt == "json":
        import json
        print(json.dumps({"messages": unread, "tasks": tasks},
                         ensure_ascii=False, indent=2))
        return

    if not unread and not has_task_section:
        print("暂无未读消息")
        return

    if unread:
        print("|发件人|收件人|日期|类型|标题|")
        print("|-----|-----|---|----|----|")
        for m in unread:
            to_str = ",".join(m["to"]) if m["to"] else "?"
            ref = f" ↩ {m['ref']}" if m["ref"] else ""
            print(f"|{m['from']}|{to_str}|{m['date']}|{m['type']}|{m['subject']}{ref}|")

    if has_task_section:
        print("\n## 任务现状")
        print(f"- 进行中 {len(tasks['in_progress'])} 件 / 阻塞 {len(tasks['blocked'])} 件")
        for b in tasks["blocked"]:
            print(f"- 阻塞：{b['name']}（{b['blocked_by']}）")
```

> 变化说明：unread 行追加了 type 与 ref 列（审计网页同源需求）；json 从裸数组改为 `{messages, tasks}`。hook 依赖的「暂无未读消息」静默串在 markdown 分支保留，行为不变。

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_check.py tests/test_write.py tests/test_task.py -v`
Expected: 全部 PASS（既有 write/task 用例不受 check 改动影响）。

- [ ] **Step 6: Commit**

```bash
git add scripts/sync.py tests/test_check.py
git commit -m "feat: sync.py check 输出任务现状段（五态统计 + 阻塞明细）"
```

---

## Task 5: derive.py 聚合引擎（与 CI 共用的同一份代码）

**Files:**
- Create: `workspaces/scripts/derive.py`
- Test: `workspaces/tests/test_derive.py`

**设计决策（写死在代码里，后续任务不得偏离）：**
- derive.py 是**纯函数 + CLI**：`scan_messages / scan_tasks`（读取层）、`render_ledger / render_task_board / build_data_json`（渲染层）。CI（board.yml）与本地、pytest 全走同一份代码。
- 信件坏 frontmatter / 任务坏 yaml → **降级**：消息保留 `{raw: ...}` 标记文件存在；任务字段全空 `{}`；渲染时照常产出该行/条目，字段显示空，绝不抛异常、不阻塞构建。
- 任务五态 → data.json 英文 state 键映射：`未开始→todo / 进行中→doing / 阻塞→blocked / 待确认→review / 已完成→done`；**非五态状态**（含坏 yaml 缺失）映射为 `"todo"` 兜底（页面五列渲染按英文键过滤，兜底保证不崩、任务不丢；lint 负责把真问题标红）。
- 消息 type 缺失默认 `邮件`；时间展示为 `MM-DD HH:mm`（从 `YYYY-MM-DD HH:mm:ss +0800` 截取）。
- **data.json 消息按文件名去重**：同一封信写给多人时 `sync.py` 会给每个收件人 inbox 各写一份**同名文件**——聚合进 data.json 时按文件名只留一份（审计网页是「公文流水」，重复同封信无意义）；而 `board/ledger/<user>.md` 按收件人分册，保留每人的全部收件（台账是「谁给我投过信」）。

**Interfaces:**
- Consumes: `sync.parse_message`（import 复用，保证与引擎同一套 frontmatter 解析）。
- Produces:
  - `scan_messages(workspaces_dir) -> list[dict]`：每项 `{file, user, from, to(list), date, subject, type, ref, raw?}`
  - `scan_tasks(workspaces_dir) -> list[dict]`：每项 `{dir, user, task, from, status, blocked_by, updated}`
  - `render_ledger(messages_of_one_user) -> str`
  - `render_task_board(all_tasks) -> str`
  - `build_data_json(messages, tasks, generated_at) -> dict`（site/app.js 契约）

- [ ] **Step 1: 写失败测试（纯函数层）**

创建 `workspaces/tests/test_derive.py`：

```python
"""derive.py 聚合与渲染纯函数。"""
import json
from pathlib import Path

import pytest
import derive
import yaml


@pytest.fixture
def fake_ws(tmp_path):
    """伪造 workspaces：alice/bob 各一封信 + 两个任务(含一个坏 yaml)。"""
    ws = tmp_path / "workspaces"
    (ws / "alice" / "inbox").mkdir(parents=True)
    (ws / "alice" / "tasks" / "任务甲").mkdir(parents=True)
    (ws / "bob" / "inbox").mkdir(parents=True)
    (ws / "bob" / "tasks" / "任务乙").mkdir(parents=True)

    (ws / "alice" / "inbox" / "2026-09-03-10-00-00-+0800-bob.md").write_text(
        "---\nfrom: bob\nto:\n  - alice\ndate: 2026-09-03 10:00:00 +0800\n"
        "subject: 协同单A\ntype: 协同单\n---\n正文\n", encoding="utf-8")
    (ws / "bob" / "inbox" / "2026-09-03-11-00-00-+0800-alice.md").write_text(
        "---\nfrom: alice\nto:\n  - bob\ndate: 2026-09-03 11:00:00 +0800\n"
        "subject: 回执B\ntype: 回执\nref: 2026-09-03-10-00-00-+0800-bob.md\n---\n正文\n",
        encoding="utf-8")
    # 坏 frontmatter 信件：不抛，照常进列表
    (ws / "alice" / "inbox" / "bad.md").write_text("这不是 frontmatter\n", encoding="utf-8")

    (ws / "alice" / "tasks" / "任务甲" / "task.yaml").write_text(
        yaml.safe_dump({"task": "任务甲", "from": "无", "status": "进行中",
                        "blocked_by": "无", "updated": "2026-09-03"},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    # 坏 yaml 任务：字段留空，不抛
    (ws / "bob" / "tasks" / "任务乙" / "task.yaml").write_text(
        "task: [未闭合\n", encoding="utf-8")
    return ws


def test_scan_messages_counts(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    assert len(msgs) == 3, "两封好信 + 一封坏 frontmatter 都要进列表"
    good = [m for m in msgs if not m.get("raw")]
    assert {m["subject"] for m in good} == {"协同单A", "回执B"}
    receipt = next(m for m in good if m["type"] == "回执")
    assert receipt["ref"] == "2026-09-03-10-00-00-+0800-bob.md"


def test_scan_tasks_degrades_bad_yaml(fake_ws):
    tasks = derive.scan_tasks(fake_ws)
    assert len(tasks) == 2
    good = next(t for t in tasks if t["dir"] == "任务甲")
    assert good["status"] == "进行中" and good["user"] == "alice"
    bad = next(t for t in tasks if t["dir"] == "任务乙")
    assert bad["status"] == "" and bad["task"] == "任务乙"


def test_build_data_json_contract(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    tasks = derive.scan_tasks(fake_ws)
    payload = derive.build_data_json(msgs, tasks, "2026-09-03T15:00:00+08:00")
    assert set(payload) == {"generated_at", "messages", "tasks"}
    assert payload["generated_at"] == "2026-09-03T15:00:00+08:00"
    # 坏 frontmatter 消息不阻塞、不进 messages(无元数据可展示)
    assert all("raw" not in m for m in payload["messages"])
    by_dir = {t["id"]: t for t in payload["tasks"]}
    assert by_dir["任务甲"]["state"] == "doing"
    assert by_dir["任务乙"]["state"] == "todo", "坏 yaml 降级为 todo 兜底"
    # 可序列化为 json
    json.dumps(payload, ensure_ascii=False)


def test_render_ledger_columns(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    alice_msgs = [m for m in msgs if m["user"] == "alice" and not m.get("raw")]
    md = derive.render_ledger(alice_msgs)
    assert "协同单A" in md and "bob" in md and "协同单" in md


def test_render_task_board_has_five_columns(fake_ws):
    tasks = derive.scan_tasks(fake_ws)
    md = derive.render_task_board(tasks)
    for s in ("未开始", "进行中", "阻塞", "待确认", "已完成"):
        assert f"## {s}" in md
    assert "任务甲" in md
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_derive.py -v`
Expected: 全部 FAIL（`ModuleNotFoundError: derive`）。

- [ ] **Step 3: 写 derive.py**

创建 `workspaces/scripts/derive.py`：

```python
"""derive.py — 派生渲染引擎（与 sync.py / board.yml 共用）

CLI:
  uv run scripts/derive.py render --workspaces <ws> [--board-dir <dir>] [--data-json <file>]
  uv run scripts/derive.py lint [--base <rev>] [--head <rev>] [--repo-root <dir>]

渲染层是纯函数：scan_messages / scan_tasks / render_ledger / render_task_board / build_data_json。
坏文件一律降级不抛：消息留 raw 标记、任务字段留空，缺字段用默认值兜底。
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml

from sync import parse_message

TASK_STATUSES = ["未开始", "进行中", "阻塞", "待确认", "已完成"]
TASK_STATUS_TO_STATE = {
    "未开始": "todo", "进行中": "doing", "阻塞": "blocked",
    "待确认": "review", "已完成": "done",
}
MSG_TYPES = ["邮件", "协同单", "回执", "退回"]


def _users(workspaces_dir: Path) -> list[Path]:
    if not workspaces_dir.exists():
        return []
    return sorted(
        p for p in workspaces_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and (p / "inbox").is_dir())


def _msg_display_time(date_str: str) -> str:
    # "2026-09-03 10:00:00 +0800" -> "09-03 10:00"
    try:
        dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%m-%d %H:%M")
    except ValueError:
        return date_str


def _to_str(to_val) -> str:
    if isinstance(to_val, list):
        return ",".join(str(t) for t in to_val)
    return str(to_val) if to_val else ""


def scan_messages(workspaces_dir: Path) -> list[dict]:
    """扫全部 inbox 文件 → 每项 {file,user,from,to,date,subject,type,ref,raw?}。"""
    out = []
    for ud in _users(workspaces_dir):
        inbox = ud / "inbox"
        for f in sorted(inbox.glob("*.md")):
            msg = parse_message(f.read_text(encoding="utf-8"))
            if "raw" in msg:
                out.append({"file": f.name, "user": ud.name, "raw": msg["raw"]})
                continue
            out.append({
                "file": f.name,
                "user": ud.name,
                "from": str(msg.get("from", "")),
                "to": msg.get("to", []),
                "date": str(msg.get("date", "")),
                "subject": str(msg.get("subject", "")),
                "type": str(msg.get("type", "邮件")),
                "ref": str(msg.get("ref", "")) or None,
            })
    return out


def scan_tasks(workspaces_dir: Path) -> list[dict]:
    """扫全部 task.yaml → 每项 {dir,user,task,from,status,blocked_by,updated}。坏 yaml 字段留空。"""
    out = []
    if not workspaces_dir.exists():
        return out
    for ud in sorted(workspaces_dir.iterdir()):
        if not ud.is_dir() or ud.name.startswith(".") or not (ud / "tasks").is_dir():
            continue
        for tdir in sorted((ud / "tasks").iterdir()):
            f = tdir / "task.yaml"
            if not f.is_file():
                continue
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            out.append({
                "dir": tdir.name,
                "user": ud.name,
                "task": str(data.get("task") or tdir.name),
                "from": str(data.get("from") or ""),
                "status": str(data.get("status") or ""),
                "blocked_by": str(data.get("blocked_by") or ""),
                "updated": str(data.get("updated") or ""),
            })
    return out


def render_ledger(messages: list[dict]) -> str:
    """单个用户的通知台账 Markdown。入参为该用户收件的消息列表。"""
    if not messages:
        return "暂无往来记录\n"
    lines = ["|时间|发件人|类型|标题|ref 链路|", "|----|------|----|----|--------|"]
    for m in messages:
        ref = f"↩ {m['ref']}" if m.get("ref") else ""
        lines.append(f"|{_msg_display_time(m['date'])}|{m['from']}|{m['type']}|{m['subject']}|{ref}|")
    return "\n".join(lines) + "\n"


def render_task_board(tasks: list[dict]) -> str:
    """全员任务看板：按五态分列。"""
    buckets: dict[str, list[dict]] = {s: [] for s in TASK_STATUSES}
    for t in tasks:
        status = t["status"] if t["status"] in TASK_STATUSES else "未开始"
        buckets[status].append(t)
    lines = []
    for s in TASK_STATUSES:
        lines.append(f"## {s}")
        items = buckets[s]
        if not items:
            lines.append("_空_\n")
            continue
        for t in items:
            blocked = f"（blocked_by: {t['blocked_by']}）" if t["status"] == "阻塞" and t["blocked_by"] else ""
            lines.append(f"- {t['task']} · @{t['user']} · from: {t['from'] or '无'} · {t['updated']} {blocked}")
        lines.append("")
    return "\n".join(lines)


def build_data_json(messages: list[dict], tasks: list[dict], generated_at: str) -> dict:
    """组装 site/app.js 的 data.json 契约（页面渲染层已定死，勿改键名）。

    按文件名去重：同一封信写给多人时,各收件人 inbox 里是同名副本,
    data.json 是「公文流水」,按文件名只留一份;ledger 才按收件人分册。
    """
    seen_files: set[str] = set()
    msgs_out = []
    for m in messages:
        if "raw" in m or m["file"] in seen_files:
            continue  # 无元数据 / 同封信的重复副本，跳过（构建不阻塞）
        seen_files.add(m["file"])
        item = {
            "id": m["file"].removesuffix(".md"),
            "type": m["type"],
            "time": _msg_display_time(m["date"]),
            "from": m["from"],
            "to": _to_str(m["to"]),
            "subject": m["subject"],
        }
        if m.get("ref"):
            item["ref"] = m["ref"]
        msgs_out.append(item)

    tasks_out = []
    for t in tasks:
        item = {
            "id": t["dir"],
            "title": t["task"],
            "owner": t["user"],
            "state": TASK_STATUS_TO_STATE.get(t["status"], "todo"),
            "updated_at": t["updated"],
        }
        if t["status"] == "阻塞" and t["blocked_by"]:
            item["blocked_by"] = t["blocked_by"]
        if t["from"] and t["from"] != "无":
            item["ref"] = t["from"]
        tasks_out.append(item)

    return {"generated_at": generated_at, "messages": msgs_out, "tasks": tasks_out}


# ---------- CLI ----------

def cmd_render(args: argparse.Namespace) -> None:
    ws = Path(args.workspaces).resolve()
    msgs = scan_messages(ws)
    tasks = scan_tasks(ws)

    if args.board_dir:
        board = Path(args.board_dir).resolve()
        board.mkdir(parents=True, exist_ok=True)
        for user in sorted({m["user"] for m in msgs}):
            user_msgs = [m for m in msgs if m["user"] == user and "raw" not in m]
            (board / "ledger").mkdir(parents=True, exist_ok=True)
            (board / "ledger" / f"{user}.md").write_text(
                f"# {user} 的通知台账\n\n" + render_ledger(user_msgs), encoding="utf-8")
        (board / "task-board.md").write_text(
            "# 全员任务看板\n\n" + render_task_board(tasks), encoding="utf-8")
        print(f"[derive] 已生成 board/ledger/*.md 与 board/task-board.md")

    if args.data_json:
        data_path = Path(args.data_json)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_data_json(msgs, tasks, datetime.now().astimezone().isoformat())
        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"[derive] 已生成 {args.data_json}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="derive.py", description="派生渲染引擎")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="聚合渲染 board/ 与 data.json")
    p_render.add_argument("--workspaces", required=True, help="workspaces 目录路径")
    p_render.add_argument("--board-dir", help="board/ 派生区输出目录(不传则不渲染 Markdown)")
    p_render.add_argument("--data-json", help="data.json 输出路径(不传则不输出)")

    p_lint = sub.add_parser("lint", help="CI lint(见 Task 6)")

    args = parser.parse_args()
    if args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "lint":
        from derive_lint import cmd_lint  # Task 6 创建
        cmd_lint(args)


if __name__ == "__main__":
    main()
```

> 说明：lint 子命令的实现在 Task 6 独立模块 `derive_lint.py` 完成，避免本文件过长。`render` 的 `--workspaces` 显式传路径，pytest 与 CI 都不依赖 cwd。

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run pytest tests/test_derive.py -v`
Expected: 6 passed（若 `import sync` 因脚本路径问题失败，在 `derive.py` 顶部先 `import sys, os; sys.path.insert(0, os.path.dirname(__file__))` 再 `from sync import parse_message`）。

- [ ] **Step 5: Commit**

```bash
git add scripts/derive.py tests/test_derive.py
git commit -m "feat: derive.py 聚合渲染引擎（台账/看板/data.json 纯函数，坏文件降级）"
```

---

## Task 6: derive lint（三条违规检测，CI 与本地共用）

**Files:**
- Create: `workspaces/scripts/derive_lint.py`
- Modify: `workspaces/scripts/derive.py`（`main` 中 lint 分支解析参数后转调）
- Test: `workspaces/tests/test_lint.py`

**lint 三条规则（Spec「CI 治理」第 4 步）：**
1. **绕过引擎写 inbox**：base..head 提交中，有改动 `workspaces/*/inbox/` 且 commit message 不符合 sync.py 生成的 `docs: <user> sends a message to <...>` 模式 → 违规。（sync.py 的提交都是该固定 message 模式，人类手写提交 message 可造假——这是"约定大于拦截"的已知妥协，lint 只做事后标红。）
2. **status 出五态**：扫描**工作树全部** `workspaces/*/tasks/*/task.yaml`，status 不在五态枚举 → 违规。
3. **非 board-bot 改 board/**：base..head 提交中，有改动 `board/` 且 commit message 不以 `[board-bot]` 前缀开头 → 违规。

**Interfaces:**
- `cmd_lint(args)` 读 `Namespace.base / head / repo_root`（默认 `base..HEAD`）
- `collect_violations(repo_root, base, head) -> list[str]`（纯逻辑，测试直接调）

- [ ] **Step 1: 写失败测试**

创建 `workspaces/tests/test_lint.py`：

```python
"""derive lint：三条违规检测（用夹具 git 历史构造违规提交）。"""
from argparse import Namespace
from pathlib import Path

import pytest
import derive_lint


def git(repo, *args):
    import subprocess
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)


def commit_file(repo, rel_path, content, message):
    p = repo / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    git(repo, "add", rel_path)
    git(repo, "commit", "-m", message)


def head_rev(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def test_lint_clean_repo(repo):
    rev = head_rev(repo)
    assert derive_lint.collect_violations(repo, rev, rev) == []


def test_lint_manual_inbox_write_flagged(repo):
    base = head_rev(repo)
    # 模拟绕过 sync.py 手工在收件箱加文件（提交信息不是 sync.py 模式）
    commit_file(repo, "workspaces/bob/inbox/hand-made.md",
                "---\nfrom: hacker\n---\n", "chore: 手工塞了一封信")
    head = head_rev(repo)
    v = derive_lint.collect_violations(repo, base, head)
    assert any("inbox" in x and "手工" in x for x in v)


def test_lint_bad_task_status_flagged(repo):
    commit_file(repo, "workspaces/alice/tasks/任务x/task.yaml",
                "task: 任务x\nstatus: 进行中x\n", "feat: 造了个坏状态")
    v = derive_lint.collect_violations(repo, "HEAD", "HEAD")
    assert any("任务x" in x and "五态" in x for x in v)


def test_lint_non_bot_board_edit_flagged(repo):
    base = head_rev(repo)
    commit_file(repo, "board/task-board.md", "手工改看板\n", "docs: 手改 board")
    head = head_rev(repo)
    v = derive_lint.collect_violations(repo, base, head)
    assert any("board" in x and "board-bot" in x for x in v)
```

> 注意：测试在夹具仓库内制造违规提交，夹具仓库是临时 `tmp_path`，不是本仓库——不违反 AGENTS 铁则（铁则管的是真实 `workspaces/<user>/inbox/`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run pytest tests/test_lint.py -v`
Expected: FAIL（`ModuleNotFoundError: derive_lint`）。其余 3 个失败（规则未实现）。

- [ ] **Step 3: 实现 derive_lint.py**

创建 `workspaces/scripts/derive_lint.py`：

```python
"""derive_lint.py — CI lint 规则（与 derive.py 的 cmd_lint 转调）"""

import argparse
import re
import subprocess
from pathlib import Path

import yaml

from sync import TASK_STATUSES, REPO_ROOT
from derive import scan_tasks, _users

SYNC_COMMIT_RE = re.compile(r"^docs: \S+ sends a message to \S+")
BOARD_BOT_PREFIX = "[board-bot]"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo_root), *args],
                          capture_output=True, text=True)


def _commits_touching(repo_root: Path, base: str, head: str, path_prefix: str) -> list[dict]:
    """返回 base..head 中改动过 path_prefix 的提交: [{rev, subject, files}]。"""
    result = _git(repo_root, "log", "--name-only", "--format=%H%x00%s",
                  f"{base}..{head}")
    commits: list[dict] = []
    cur: dict | None = None
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        if "\x00" in line:
            rev, subject = line.split("\x00", 1)
            cur = {"rev": rev, "subject": subject, "files": []}
            commits.append(cur)
        elif cur is not None:
            if line.startswith(path_prefix):
                cur["files"].append(line)
    return [c for c in commits if c["files"]]


def collect_violations(repo_root: Path, base: str, head: str) -> list[str]:
    problems: list[str] = []
    ws_dir = repo_root / "workspaces"

    # 规则1: 绕过引擎写 inbox
    for c in _commits_touching(repo_root, base, head, "workspaces/"):
        inbox_files = [f for f in c["files"] if "/inbox/" in f]
        if inbox_files and not SYNC_COMMIT_RE.match(c["subject"]):
            problems.append(
                f"绕过 sync.py 直接改动收件箱: {c['rev'][:8]} {c['subject']} "
                f"-> {','.join(inbox_files)}")

    # 规则2: status 出五态（工作树全量）
    for t in scan_tasks(ws_dir):
        if t["status"] and t["status"] not in TASK_STATUSES:
            problems.append(
                f"任务 {t['dir']}(@{t['user']}) status 出五态: {t['status']}")

    # 规则3: 非 board-bot 改 board/
    for c in _commits_touching(repo_root, base, head, "board/"):
        if not c["subject"].startswith(BOARD_BOT_PREFIX):
            problems.append(
                f"非 board-bot 改动派生区 board/: {c['rev'][:8]} {c['subject']}")

    return problems


def cmd_lint(args: argparse.Namespace) -> None:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else REPO_ROOT
    base = args.base or "HEAD"
    head = args.head or "HEAD"
    problems = collect_violations(repo_root, base, head)
    if problems:
        print("[lint] 违规项:")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)
    print("[lint] OK")
```

- [ ] **Step 4: derive.py 的 lint 分支补参数**

在 `derive.py` 的 `p_lint = sub.add_parser(...)` 之后补：

```python
    p_lint.add_argument("--base", help="起始 rev(默认 HEAD)")
    p_lint.add_argument("--head", help="结束 rev(默认 HEAD)")
    p_lint.add_argument("--repo-root", help="仓库根(默认取 sync.REPO_ROOT)")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run pytest tests/test_lint.py -v`
Expected: 4 passed。再全量回归：`uv run pytest` → 全绿。

- [ ] **Step 6: Commit**

```bash
git add scripts/derive.py scripts/derive_lint.py tests/test_lint.py
git commit -m "feat: derive lint 三条规则（inbox 绕过/五态/board-bot）"
```

---

## Task 7: CI 治理 workflow（.github/workflows/board.yml）+ .gitignore

**Files:**
- Create: `.github/workflows/board.yml`
- Modify: `.gitignore`（追加 `site/data.json`——本地预览生成的派生产物不进 git）
- Test: 本任务无 pytest（workflow YAML 无法本地单测；验证 = `python -c "import yaml; yaml.safe_load(...)"` 语法正确 + 步骤与 PRD 五步逐条对应）

**PRD 五步对应表（写死在 workflow 注释里）：**

| PRD 步骤 | workflow job/step |
|---|---|
| 触发: push main + 防环 | `on.push.branches=[main]` + job 级 `if: github.actor != 'github-actions[bot]'` |
| 1 聚合 | `derive.py render`（scan 全量 inbox + task.yaml） |
| 2 渲染 Markdown | 同一步骤的 `--board-dir` 输出 |
| 3 渲染网页产物 | 同一步骤的 `--data-json` 输出，与 `site/` 一起打包 Pages |
| 4 lint | `derive.py lint --base ${{ github.event.before }} --head ${{ github.sha }}` |
| 5 发布 | 步骤「commit board」以 `[board-bot]` 回提 + `deploy-pages` |

- [ ] **Step 1: 写 workflow**

创建 `.github/workflows/board.yml`：

```yaml
name: board

on:
  push:
    branches: [main]

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  board:
    runs-on: ubuntu-latest
    # 防环: board-bot 自己的提交不再触发本 workflow
    if: github.actor != 'github-actions[bot]'
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0   # lint 需要 base..head 历史

      - uses: astral-sh/setup-uv@v4
        with:
          enable-cache: true

      - name: 安装依赖 (PyYAML)
        run: |
          cd workspaces
          uv sync

      - name: 聚合渲染（board/ + _site/data.json）+ 组装发布目录
        run: |
          mkdir -p "$GITHUB_WORKSPACE/_site"
          cp site/index.html site/app.js "$GITHUB_WORKSPACE/_site/"
          cd workspaces
          uv run scripts/derive.py render \
            --workspaces "$GITHUB_WORKSPACE/workspaces" \
            --board-dir "$GITHUB_WORKSPACE/board" \
            --data-json "$GITHUB_WORKSPACE/_site/data.json"
          echo "发布目录内容:" && ls -la "$GITHUB_WORKSPACE/_site"

      - name: lint 质检（违规即标红）
        run: |
          cd workspaces
          uv run scripts/derive.py lint \
            --repo-root "$GITHUB_WORKSPACE" \
            --base "${{ github.event.before }}" \
            --head "${{ github.sha }}"

      - name: board-bot 回提派生区 Markdown
        run: |
          if [ -n "$(git status --porcelain board)" ]; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git add board
            git commit -m "[board-bot] 更新派生区台账与看板"
            git pull --rebase origin main
            git push
          else
            echo "board/ 无变化,跳过回提"
          fi

      - name: 发布网页 (github.io)
        uses: actions/upload-pages-artifact@v3
        with:
          path: _site
      - id: deployment
        name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

> 路径说明：`site/` 为前端**源码**（index.html + app.js，已提交）；`data.json` 为 CI 生成产物，放 `_site/` 发布目录，与 `site/` 静态文件拼成 Pages 产物，**都不进 git**。`board/` Markdown 派生区由 board-bot 回提仓库（客户端只读）。

- [ ] **Step 2: .gitignore 追加**

在 `.gitignore` 末尾追加（生成物不进版本库）：

```gitignore
# 本地预览/CI 派生产物
site/data.json
_site/
```

- [ ] **Step 3: 验证 workflow YAML 语法与步骤对应**

Run:
```bash
python3 -c "import yaml, pathlib; d=yaml.safe_load(pathlib.Path('.github/workflows/board.yml').read_text()); jobs=list(d['jobs']); print('jobs:', jobs); assert 'board' in jobs; print('ok')"
```
Expected: `jobs: ['board']` + `ok`。

- [ ] **Step 4: 全量回归**

Run: `uv run pytest` → 全绿。

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/board.yml .gitignore
git commit -m "feat: board.yml CI 治理（聚合→渲染→lint→board-bot 回提→Pages 发布）"
```

---

## Task 8: 本地端到端验证（含真实数据 data.json 生成）

**目标（对应纪要「下一步」最后一条）**：pytest 全绿 + 真实仓库跑通 derive 渲染出 data.json + 三视图可加载。

**Files:** 无新增代码；验证命令。**临时产物只落在 /tmp 或 _site/，一律不进 git，验证后清理。**

- [ ] **Step 1: pytest 全量回归**

Run: `uv run pytest`
Expected: 全绿（write/task/check/derive/lint 全部用例通过）。

- [ ] **Step 2: 在真实仓库执行一次聚合渲染（只读派生，产物进 /tmp）**

Run:
```bash
cd /Users/xincheng/workspaces/llm-project/src/message-board
mkdir -p /tmp/mb-e2e/board /tmp/mb-e2e/site
cd workspaces && uv run scripts/derive.py render \
  --workspaces "$PWD" \
  --board-dir /tmp/mb-e2e/board \
  --data-json /tmp/mb-e2e/data.json
cp ../site/index.html ../site/app.js /tmp/mb-e2e/site/
ls -R /tmp/mb-e2e
```
Expected: `/tmp/mb-e2e/board/ledger/{mingyi,oliviadu}.md`、`board/task-board.md`、`data.json`、`site/` 出现。

- [ ] **Step 3: data.json 契约校验**

Run:
```bash
python3 - <<'PY'
import json
d = json.load(open('/tmp/mb-e2e/data.json', encoding='utf-8'))
assert set(d) == {'generated_at', 'messages', 'tasks'}
for m in d['messages']:
    assert set(m) >= {'id', 'type', 'time', 'from', 'to', 'subject'}
print('messages:', len(d['messages']), 'tasks:', len(d['tasks']))
states = {t['state'] for t in d['tasks']}
assert states <= {'todo','doing','blocked','review','done'}
print('ok')
PY
```
Expected: `ok`（真实仓库里 mingyi/oliviadu 的信件被聚合为 messages；若尚无任务，tasks 可能为空列表，不报错）。

- [ ] **Step 4: 起本地静态服务器验证三视图可加载（data.json 可 fetch）**

Run:
```bash
# 模拟发布目录布局: index.html / app.js / data.json 三者同根(_site 即站点根)
mkdir -p /tmp/mb-e2e/_site
cp /tmp/mb-e2e/data.json /tmp/mb-e2e/site/index.html /tmp/mb-e2e/site/app.js /tmp/mb-e2e/_site/
cd /tmp/mb-e2e/_site && python3 -m http.server 8931 >/dev/null 2>&1 &
sleep 1
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8931/index.html   # 期望 200
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8931/data.json     # 期望 200
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8931/app.js        # 期望 200
kill %1
```
Expected: `200 200 200`。

> 浏览器渲染三视图的最终人工确认（截图核对）留给用户在有 GUI 的环境执行：打开 `http://127.0.0.1:8931/`（index.html 与 data.json 同根的发布布局）看三视图与真实数据。本步已验证「页面资源与数据均可访问」，若环境有 playwright/无头浏览器，可补充 `npx playwright screenshot` 自动截图核对。

- [ ] **Step 5: 验证仓库未被派生产物污染**

Run: `git status --porcelain`
Expected: 只有本计划各 Task 的代码/文档提交；`site/data.json`、`board/`、`_site/` 不出现（.gitignore 已覆盖；本次验证产物全在 /tmp）。

- [ ] **Step 6: 收尾提交本计划文档（若执行会话尚未提交）**

```bash
git add docs/superpowers/plans/2026-09-03-collab-audit-upgrade.md
git commit -m "docs: 协作审计升级实施方案（TDD 任务拆解）"
```

---

## Self-Review 结论（写计划时自查）

- **Spec 覆盖**：写 `--type/--ref`（PRD 设计规则 write 段）→ Task 2；task 五态与 create/update/list → Task 3；check 任务现状 → Task 4；聚合/台账/看板/data.json 生成函数与坏 yaml 降级（测试清单）→ Task 5；CI lint 三条 → Task 6；board.yml 五步 + 防环 + 现实妥协 → Task 7；端到端 → Task 8。site/ 视觉与三视图已定稿（不属本计划改动范围）。
- **placeholder 扫描**：无 TBD/TODO；每步含可执行命令与代码。
- **类型一致性**：`TASK_STATUSES`、`load_task_yaml`、`scan_messages` 等签名跨 Task 3/4/5/6 一致（derive 从 sync 导入 parse_message 与 TASK_STATUSES）；`render` CLI 参数 `--workspaces/--board-dir/--data-json` 在 Task 5/7/8 三处一致；`build_data_json` 键名与 `site/app.js` 注释契约逐键对齐。
