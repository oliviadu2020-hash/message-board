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
