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
