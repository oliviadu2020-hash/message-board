import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from sync import (
    build_frontmatter,
    check,
    extract_sender,
    extract_subject,
    generate_filename,
    send,
)


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
    assert "date: 20" in result or "date: '20" in result


class TestSend:
    def test_send_writes_file_and_git(self, tmp_path):
        """Verify send writes file to workspaces/<to>/inbox/ + git ops"""
        # git repo setup
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        (repo / "workspaces" / "alice").mkdir(parents=True)
        (repo / "workspaces" / "bob" / "inbox").mkdir(parents=True)

        args = MagicMock()
        args.repo = str(repo)
        args.to = "bob"
        args.from_user = "alice"
        args.subject = "test message"
        args.content = "hello bob"
        args.file = None

        # run with push mocked (no real remote)
        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = send(args)

        assert result == 0

        # verify file written
        expected = repo / "workspaces" / "bob" / "inbox" / "alice-test-message.md"
        assert expected.exists()
        text = expected.read_text()
        assert "from: alice" in text
        assert "to: bob" in text
        assert "subject: test message" in text
        assert "hello bob" in text

    def test_send_no_workspaces_dir(self, tmp_path):
        """Error when workspaces/ doesn't exist"""
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)

        args = MagicMock()
        args.repo = str(repo)
        args.to = "bob"
        args.from_user = "alice"
        args.subject = "hi"
        args.content = "x"
        args.file = None

        assert send(args) == 1

    def test_send_to_nonexistent_inbox(self, tmp_path):
        """Creates inbox on demand"""
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        (repo / "workspaces" / "alice").mkdir(parents=True)
        # workspaces/bob 不存在，inbox 应被创建

        args = MagicMock()
        args.repo = str(repo)
        args.to = "bob"
        args.from_user = "alice"
        args.subject = "hello"
        args.content = "x"
        args.file = None

        with patch("subprocess.run", autospec=True) as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = send(args)

        assert result == 0
        assert (repo / "workspaces" / "bob" / "inbox" / "alice-hello.md").exists()


class TestCheck:
    def test_check_no_workspaces_dir(self, tmp_path):
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        args = MagicMock()
        args.repo = str(repo)
        args.user = "alice"
        assert check(args) == 2

    def test_check_no_inbox(self, tmp_path):
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        (repo / "workspaces" / "alice").mkdir(parents=True)
        args = MagicMock()
        args.repo = str(repo)
        args.user = "alice"
        assert check(args) == 2  # no inbox → error

    def test_check_empty_inbox(self, tmp_path):
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        (repo / "workspaces" / "alice" / "inbox").mkdir(parents=True)
        args = MagicMock()
        args.repo = str(repo)
        args.user = "alice"
        assert check(args) == 1  # empty → no mail

    def test_check_with_messages(self, tmp_path):
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        inbox = repo / "workspaces" / "alice" / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "bob-hello.md").write_text(
            "---\nfrom: bob\nsubject: hi\n---\nhello"
        )
        args = MagicMock()
        args.repo = str(repo)
        args.user = "alice"
        assert check(args) == 0  # new mail

    def test_check_seen_persists(self, tmp_path):
        repo = tmp_path / "mb"
        repo.mkdir()
        init_repo(repo)
        inbox = repo / "workspaces" / "alice" / "inbox"
        inbox.mkdir(parents=True)
        (inbox / "bob-hello.md").write_text(
            "---\nfrom: bob\nsubject: hi\n---\nhello"
        )
        args = MagicMock()
        args.repo = str(repo)
        args.user = "alice"
        # first run: new mail (0)
        assert check(args) == 0
        # second run: already seen (1)
        assert check(args) == 1


def test_extract_sender_subject():
    text = "---\nfrom: alice\nsubject: test\n---\n"
    assert extract_sender(text) == "alice"
    assert extract_subject(text) == "test"


def init_repo(repo_path):
    """Initialize a git repo without git config setup"""
    subprocess.run(["git", "init", "-q", "-b", "master"], cwd=repo_path)
    (repo_path / ".gitignore").write_text("placeholder\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo_path)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo_path)
