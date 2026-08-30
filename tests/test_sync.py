from datetime import datetime

from sync import build_frontmatter, generate_filename


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
