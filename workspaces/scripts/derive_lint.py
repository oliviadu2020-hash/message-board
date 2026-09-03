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
