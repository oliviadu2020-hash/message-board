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
