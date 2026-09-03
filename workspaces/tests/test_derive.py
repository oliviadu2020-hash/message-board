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
    # 新契约：messages 不再内嵌，page_* 元头 + stats/tasks
    assert "messages" not in payload, "data.json 不应内嵌 messages 数组(分页时代)"
    assert set(payload) == {"generated_at", "total_messages", "page_size", "page_count",
                            "msg_stats", "msg_ranking", "tasks"}
    assert payload["generated_at"] == "2026-09-03T15:00:00+08:00"
    assert payload["page_size"] == 10
    # fake_ws 有两封好信(坏 frontmatter 不计入)：page_count=1、total=2
    assert payload["total_messages"] == 2
    assert payload["page_count"] == 1
    by_dir = {t["id"]: t for t in payload["tasks"]}
    assert by_dir["任务甲"]["state"] == "doing"
    assert by_dir["任务乙"]["state"] == "todo", "坏 yaml 降级为 todo 兜底"
    # stats 头部全局预聚合，概览统计不依赖分页位置
    assert payload["msg_stats"]["total"] == 2
    assert payload["msg_stats"]["协同单"] == 1 and payload["msg_stats"]["回执"] == 1
    assert payload["msg_ranking"][0]["n"] >= 1, "活跃度排行至少一项"
    # 可序列化为 json
    json.dumps(payload, ensure_ascii=False)


def test_split_pages_by_time_desc_and_size_10(tmp_path):
    """12 封信 → 每页 10 条 → 2 页;切出来的页按时间倒序。"""
    import derive as d

    ws = tmp_path / "workspaces"
    (ws / "alice" / "inbox").mkdir(parents=True)
    # 造 12 封带递增时间戳的信
    for i in range(12):
        (ws / "alice" / "inbox" / f"2026-09-{i+1:02d}-10-00-00-+0800-bob.md").write_text(
            f"---\nfrom: bob\nto:\n  - alice\ndate: 2026-09-{i+1:02d} 10:00:00 +0800\n"
            f"subject: 信{i}\ntype: 邮件\n---\n正文\n", encoding="utf-8")
    msgs = d.scan_messages(ws)
    pages = d.split_msgs_pages(msgs, page_size=10)
    assert len(pages) == 2, f"12 条 / 每页 10 应得 2 页,得到 {len(pages)}"
    assert len(pages[0]) == 10 and len(pages[1]) == 2
    # 时间倒序:第 1 页第一条是 09-12(最新),最后一条是 09-03
    assert pages[0][0]["time"] == "09-12 10:00", f"应最新在前,得到 {pages[0][0]}"
    assert pages[0][-1]["time"] == "09-03 10:00"
    assert pages[1][0]["time"] == "09-02 10:00"
    assert pages[1][-1]["time"] == "09-01 10:00", f"应最旧在后,得到 {pages[1][-1]}"
    # 每页条目为前端展示字段 id(去.md)/time/from/to/subject/type(兼容可选 ref)
    assert pages[0][0]["id"] == "2026-09-12-10-00-00-+0800-bob"


def test_build_pages_and_contract_parallel(tmp_path):
    """同一份输入:split 与 build_data_json 给出一致的页数与总量。"""
    ws = tmp_path / "workspaces"
    (ws / "alice" / "inbox").mkdir(parents=True)
    for i in range(23):
        (ws / "alice" / "inbox" / f"2026-09-{i+1:02d}-10-00-00-+0800-bob.md").write_text(
            f"---\nfrom: bob\nto:\n  - alice\ndate: 2026-09-{i+1:02d} 10:00:00 +0800\n"
            f"subject: 信{i}\ntype: 邮件\n---\n正文\n", encoding="utf-8")
    msgs = derive.scan_messages(ws)
    payload = derive.build_data_json(msgs, [], "2026-09-03T15:00:00+08:00")
    pages = derive.split_msgs_pages(msgs, page_size=10)
    assert payload["total_messages"] == 23
    assert payload["page_count"] == 3       # 23 / 10 → 3 页
    assert len(pages) == 3
    # 每页都是一个合法消息对象列表(id/time/from/to/subject/type)
    for pg in pages:
        for item in pg:
            assert set(item) >= {"id", "type", "time", "from", "to", "subject"}


def test_build_data_json_dedupes_multi_recipient_copies(fake_ws):
    """同一封信投给多人时各收件人 inbox 是同名副本，分页流水只留一份。"""
    # alice 的 inbox 里再放一封与 bob 的 回执B 同名的信(模拟群发副本)
    dup = fake_ws / "alice" / "inbox" / "2026-09-03-11-00-00-+0800-alice.md"
    dup.write_text(
        "---\nfrom: alice\nto:\n  - alice\n  - bob\ndate: 2026-09-03 11:00:00 +0800\n"
        "subject: 回执B\ntype: 回执\nref: 2026-09-03-10-00-00-+0800-bob.md\n---\n正文\n",
        encoding="utf-8")
    msgs = derive.scan_messages(fake_ws)
    payload = derive.build_data_json(msgs, [], "2026-09-03T15:00:00+08:00")
    # 两封合法信(协同单A + 回执B)，其中一个收件人 side 的副本去掉
    assert payload["total_messages"] == 2, "同名副本必须去重，总数按唯一文件名计 2"


def test_render_ledger_columns(fake_ws):
    msgs = derive.scan_messages(fake_ws)
    alice_msgs = [m for m in msgs if m["user"] == "alice" and not m.get("raw")]
    md = derive.render_ledger(alice_msgs)
    assert "协同单A" in md and "bob" in md and "协同单" in md


def test_render_ledger_desc_by_time(fake_ws):
    """台账必须按时间倒序（PRD: 按时间倒序列出每封信）。"""
    older = {"user": "alice", "date": "2026-09-02 09:00:00 +0800",
             "from": "bob", "type": "邮件", "subject": "旧信", "ref": None}
    newer = {"user": "alice", "date": "2026-09-03 09:00:00 +0800",
             "from": "bob", "type": "邮件", "subject": "新信", "ref": None}
    md = derive.render_ledger([older, newer])
    assert md.index("新信") < md.index("旧信"), "最新信件应排最前"


def test_render_task_board_has_five_columns(fake_ws):
    tasks = derive.scan_tasks(fake_ws)
    md = derive.render_task_board(tasks)
    for s in ("未开始", "进行中", "阻塞", "待确认", "已完成"):
        assert f"## {s}" in md
    assert "任务甲" in md
