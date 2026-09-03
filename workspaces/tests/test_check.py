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


def test_check_unread_and_tasks_both_shown(repo, capsys):
    # bob 给 alice 投一封信（切身份真实走引擎）
    (repo / "workspaces" / ".current_user").write_text("bob", encoding="utf-8")
    sync.cmd_write(Namespace(to="alice", subject="新需求", content="正文",
                             file=None, type="协同单", ref=None))
    (repo / "workspaces" / ".current_user").write_text("alice", encoding="utf-8")
    run_create(repo, "进行中的活")
    run_update(repo, "进行中的活", status="进行中")
    out = run_check(repo, capsys)
    assert "新需求" in out
    assert "## 任务现状" in out
    assert "进行中 1 件 / 阻塞 0 件" in out
