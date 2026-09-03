"""task 子命令组：create / update / list。"""
from argparse import Namespace
from datetime import datetime

import pytest
import sync
import yaml


def task_yaml(repo, user, name):
    return repo / "workspaces" / user / "tasks" / name / "task.yaml"


def run_create(repo, name, upstream=None):
    cmd = Namespace(name=name, from_file=upstream)
    sync.cmd_task_create(cmd)
    return task_yaml(repo, "alice", name)


def test_task_create_defaults(repo):
    f = run_create(repo, "下单锁库存联调")
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    assert data["task"] == "下单锁库存联调"
    assert data["status"] == "未开始"
    assert data["blocked_by"] == "无"
    assert data["from"] == "无"
    assert data["updated"] == datetime.now().strftime("%Y-%m-%d")


def test_task_create_with_from(repo):
    f = run_create(repo, "对账联调", upstream="2026-09-03-10-00-00-+0800-bob.md")
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    assert data["from"] == "inbox/2026-09-03-10-00-00-+0800-bob.md"


def test_task_create_dup_rejected(repo):
    run_create(repo, "重名任务")
    before = sorted((repo / "workspaces" / "alice" / "tasks").glob("*/task.yaml"))
    with pytest.raises(SystemExit):
        run_create(repo, "重名任务")
    after = sorted((repo / "workspaces" / "alice" / "tasks").glob("*/task.yaml"))
    assert before == after, "重复创建不得产生第二个任务包"


def test_task_create_bad_name_rejected(repo):
    with pytest.raises(SystemExit):
        run_create(repo, "a/b")
    assert not (repo / "workspaces" / "alice" / "tasks" / "a" / "b").exists()


def test_task_update_status(repo):
    run_create(repo, "联调任务")
    sync.cmd_task_update(Namespace(name="联调任务", status="进行中", blocked=None))
    data = yaml.safe_load(task_yaml(repo, "alice", "联调任务").read_text(encoding="utf-8"))
    assert data["status"] == "进行中"
    assert data["blocked_by"] == "无", "非阻塞态 blocked_by 应复位为无"


def test_task_update_invalid_status_rejected(repo):
    run_create(repo, "联调任务")
    with pytest.raises(SystemExit):
        sync.cmd_task_update(Namespace(name="联调任务", status="瞎写", blocked=None))
    data = yaml.safe_load(task_yaml(repo, "alice", "联调任务").read_text(encoding="utf-8"))
    assert data["status"] == "未开始", "非法状态不得写入"


def test_task_update_blocked(repo):
    run_create(repo, "联调任务")
    sync.cmd_task_update(Namespace(name="联调任务", status="阻塞", blocked="等 bob 回执"))
    data = yaml.safe_load(task_yaml(repo, "alice", "联调任务").read_text(encoding="utf-8"))
    assert data["status"] == "阻塞"
    assert data["blocked_by"] == "等 bob 回执"


def test_task_update_missing_task_rejected(repo):
    with pytest.raises(SystemExit):
        sync.cmd_task_update(Namespace(name="不存在", status="进行中", blocked=None))


def test_task_list_markdown(repo, capsys):
    run_create(repo, "任务甲")
    run_create(repo, "任务乙")
    sync.cmd_task_update(Namespace(name="任务甲", status="进行中", blocked=None))
    sync.cmd_task_list(Namespace(fmt="markdown"))
    out = capsys.readouterr().out
    assert "任务甲" in out and "任务乙" in out and "进行中" in out and "未开始" in out


def test_task_list_json(repo, capsys):
    run_create(repo, "任务甲")
    sync.cmd_task_list(Namespace(fmt="json"))
    rows = __import__("json").loads(capsys.readouterr().out)
    assert rows[0]["task"] == "任务甲"
    assert rows[0]["status"] == "未开始"
