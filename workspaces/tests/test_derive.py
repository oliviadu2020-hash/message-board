"""derive.py 聚合与渲染纯函数。"""
import json
from pathlib import Path

import pytest
import derive
import yaml


@pytest.fixture
def fake_ws(tmp_path):
    """伪造 workspaces：alice/bob 各一封信 + 两个任务(含一个坏 yaml)。"""
    ws = tmp_path / "workspaces"
    (ws / "alice" / "inbox").mkdir(parents=True)
    (ws / "alice" / "tasks" / "任务甲").mkdir(parents=True)
    (ws / "bob" / "inbox").mkdir(parents=True)
    (ws / "bob" / "tasks" / "任务乙").mkdir(parents=True)

    (ws / "alice" / "inbox" / "2026-09-03-10-00-00-+0800-bob.md").write_text(
        "---\nfrom: bob\nto:\n  - alice\ndate: 2026-09-03 10:00:00 +0800\n"
        "subject: 协同单A\ntype: 协同单\n---\n正文\n", encoding="utf-8")
    (ws / "bob" / "inbox" / "2026-09-03-11-00-00-+0800-alice.md").write_text(
        "---\nfrom: alice\nto:\n  - bob\ndate: 2026-09-03 11:00:00 +0800\n"
        "subject: 回执B\ntype: 回执\nref: 2026-09-03-10-00-00-+0800-bob.md\n---\n正文\n",
        encoding="utf-8")
    # 坏 frontmatter 信件：不抛，照常进列表
    (ws / "alice" / "inbox" / "bad.md").write_text("这不是 frontmatter\n", encoding="utf-8")

    (ws / "alice" / "tasks" / "任务甲" / "task.yaml").write_text(
        yaml.safe_dump({"task": "任务甲", "from": "无", "status": "进行中",
                        "blocked_by": "无", "updated": "2026-09-03"},
                       allow_unicode=True, sort_keys=False), encoding="utf-8")
    # 坏 yaml 任务：字段留空，不抛
    (ws / "bob" / "tasks" / "任务乙" / "task.yaml").write_text(
        "task: [未闭合\n", encoding="utf-8")
    return ws


def test_scan_messages_counts(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    assert len(msgs) == 3, "两封好信 + 一封坏 frontmatter 都要进列表"
    good = [m for m in msgs if not m.get("raw")]
    assert {m["subject"] for m in good} == {"协同单A", "回执B"}
    receipt = next(m for m in good if m["type"] == "回执")
    assert receipt["ref"] == "2026-09-03-10-00-00-+0800-bob.md"


def test_scan_tasks_degrades_bad_yaml(fake_ws):
    tasks = derive.scan_tasks(fake_ws)
    assert len(tasks) == 2
    good = next(t for t in tasks if t["dir"] == "任务甲")
    assert good["status"] == "进行中" and good["user"] == "alice"
    bad = next(t for t in tasks if t["dir"] == "任务乙")
    assert bad["status"] == "" and bad["task"] == "任务乙"


def test_build_data_json_contract(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    tasks = derive.scan_tasks(fake_ws)
    payload = derive.build_data_json(msgs, tasks, "2026-09-03T15:00:00+08:00")
    assert set(payload) == {"generated_at", "messages", "tasks"}
    assert payload["generated_at"] == "2026-09-03T15:00:00+08:00"
    # 坏 frontmatter 消息不阻塞、不进 messages(无元数据可展示)
    assert all("raw" not in m for m in payload["messages"])
    by_dir = {t["id"]: t for t in payload["tasks"]}
    assert by_dir["任务甲"]["state"] == "doing"
    assert by_dir["任务乙"]["state"] == "todo", "坏 yaml 降级为 todo 兜底"
    # 可序列化为 json
    json.dumps(payload, ensure_ascii=False)


def test_build_data_json_dedupes_multi_recipient_copies(fake_ws):
    """同一封信投给多人时各收件人 inbox 是同名副本，data.json 只留一份。"""
    # alice 的 inbox 里再放一封与 bob 的 回执B 同名的信(模拟群发副本)
    dup = fake_ws / "alice" / "inbox" / "2026-09-03-11-00-00-+0800-alice.md"
    dup.write_text(
        "---\nfrom: alice\nto:\n  - alice\n  - bob\ndate: 2026-09-03 11:00:00 +0800\n"
        "subject: 回执B\ntype: 回执\nref: 2026-09-03-10-00-00-+0800-bob.md\n---\n正文\n",
        encoding="utf-8")
    msgs = derive.scan_messages(fake_ws)
    payload = derive.build_data_json(msgs, [], "2026-09-03T15:00:00+08:00")
    ids = [m["id"] for m in payload["messages"]]
    assert len(ids) == len(set(ids)), "同名副本必须去重"
    assert ids.count("2026-09-03-11-00-00-+0800-alice") == 1


def test_render_ledger_columns(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    alice_msgs = [m for m in msgs if m["user"] == "alice" and not m.get("raw")]
    md = derive.render_ledger(alice_msgs)
    assert "协同单A" in md and "bob" in md and "协同单" in md


def test_render_task_board_has_five_columns(fake_ws):
    tasks = derive.scan_tasks(fake_ws)
    md = derive.render_task_board(tasks)
    for s in ("未开始", "进行中", "阻塞", "待确认", "已完成"):
        assert f"## {s}" in md
    assert "任务甲" in md
