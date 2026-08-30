import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from sync import build_frontmatter, generate_filename, send


def test_import():
    """sync.py module can be imported"""
    import sync
    assert True


def test_generate_filename_slugged():
    assert generate_filename("alice", "issue-42 fix the bug") == \
        "alice-issue-42-fix-the-bug.md"


def test_generate_filename_spaces_and_case():
    assert generate_filename("bob", "Fix Critical Security Issue!") == \
        "bob-fix-critical-security-issue.md"


def test_generate_filename_short():
    assert generate_filename("alice", "hi") == \
        "alice-hi.md"


def test_generate_filename_unicode_safe():
    assert generate_filename("alice", "修复安全问题！！！") == \
        "alice-修复安全问题.md"


def test_build_frontmatter_format():
    result = build_frontmatter("alice", "bob", "test msg")
    assert result.startswith("---\n")
    assert result.endswith("---\n\n")
    assert "from: alice\n" in result
    assert "to: bob\n" in result
    assert "subject: test msg\n" in result
    # ISO 格式年份前缀检查（yaml输出含引号）
    assert "date: '20" in result or 'date: 20' in result


def test_send_writes_file_and_git(tmp_path):
    """verify: file written to messages/<to>/ + git add/commit/push"""
    # git repo
    import subprocess
    subprocess.run(["git", "init", "-b", "master"], cwd=tmp_path, capture_output=True)
    # must have one prior commit to enable later git operations
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "README.md"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    (tmp_path / "messages" / "bob").mkdir(parents=True)

    # mock args from argparse
    args = MagicMock()
    args.repo = str(tmp_path)
    args.to = "bob"
    args.from_user = "alice"
    args.subject = "test message"
    args.content = "hello bob"
    args.file = None

    # run（mock push 避免本地 remote 依赖）
    with patch("sync.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = send(args)

    assert result == 0

    # file exists + frontmatter + content
    expected = tmp_path / "messages" / "bob" / "alice-test-message.md"
    assert expected.exists()
    text = expected.read_text()
    assert "from: alice" in text
    assert "to: bob" in text
    assert "hello bob" in text

    # git: added + committed
    result = subprocess.run(
        ["git", "log", "--oneline"],
        cwd=tmp_path, capture_output=True, text=True
    )
    assert "msg: test message" in result.stdout
