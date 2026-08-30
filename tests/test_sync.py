import subprocess
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from sync import build_frontmatter, generate_filename, send


def test_import():
    """sync.py module can be imported"""
    import sync


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

    # run
    real_run = subprocess.run

    def mock_run(cmd, **kwargs):
        # 只拦截 git push，其它子进程正常执行
        if cmd[-1] == "push":
            class R: returncode = 0; stderr = ""; stdout = ""
            return R()
        return real_run(cmd, **kwargs)

    with patch("subprocess.run", side_effect=mock_run):
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

class TestCheck:
    def test_check_empty_repo(self, tmp_path):
        """空 repo：无消息目录 → error"""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "/tmp/origin-repo"], cwd=tmp_path, capture_output=True)
        args = MagicMock()
        args.repo = str(tmp_path)
        args.user = "alice"
        from sync import check as sync_check
        assert sync_check(args) == 2

    def test_check_no_messages(self, tmp_path):
        """只设计 messages/alice/ 空目录 → no mail"""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "/tmp/origin-repo"], cwd=tmp_path, capture_output=True)
        (tmp_path / "messages" / "alice").mkdir(parents=True)
        args = MagicMock()
        args.repo = str(tmp_path)
        args.user = "alice"
        from sync import check as sync_check
        assert sync_check(args) == 1

    def test_check_with_messages(self, tmp_path):
        """messages/alice/ 有文件 → new mail，exit 0"""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "/tmp/origin-repo"], cwd=tmp_path, capture_output=True)
        inbox = tmp_path / "messages" / "alice"
        inbox.mkdir(parents=True)
        (inbox / "bob-hello.md").write_text("---\nfrom: bob\nsubject: hi\n---\n")
        args = MagicMock()
        args.repo = str(tmp_path)
        args.user = "alice"
        from sync import check as sync_check
        assert sync_check(args) == 0

    def test_check_seen_persists(self, tmp_path):
        """第二次 check 后无新邮件（seen 已保存）"""
        import subprocess
        subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "/tmp/origin-repo"], cwd=tmp_path, capture_output=True)
        inbox = tmp_path / "messages" / "alice"
        inbox.mkdir(parents=True)
        (inbox / "bob-hello.md").write_text("---\nfrom: bob\nsubject: hi\n---\n")
        args = MagicMock()
        args.repo = str(tmp_path)
        args.user = "alice"
        from sync import check as sync_check
        # first run: seen file registered, exit 0
        assert sync_check(args) == 0
        # second run: no new mail, exit 1
        assert sync_check(args) == 1
