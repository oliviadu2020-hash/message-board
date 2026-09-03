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
    # 当前(升级前)行为: 无 type 字段；subject 正常写入
    assert "type" not in text.split("---")[1]
    assert "subject: 排期" in text
