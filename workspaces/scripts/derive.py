"""derive.py — 派生渲染引擎（与 sync.py / board.yml 共用）

CLI:
  uv run scripts/derive.py render --workspaces <ws> [--board-dir <dir>] [--data-json <file>]
  uv run scripts/derive.py lint [--base <rev>] [--head <rev>] [--repo-root <dir>]

渲染层是纯函数：scan_messages / scan_tasks / render_ledger / render_task_board / build_data_json。
坏文件一律降级不抛：消息留 raw 标记、任务字段留空，缺字段用默认值兜底。
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

import yaml

from sync import parse_message

TASK_STATUSES = ["未开始", "进行中", "阻塞", "待确认", "已完成"]
TASK_STATUS_TO_STATE = {
    "未开始": "todo", "进行中": "doing", "阻塞": "blocked",
    "待确认": "review", "已完成": "done",
}
MSG_TYPES = ["邮件", "协同单", "回执", "退回"]


def _users(workspaces_dir: Path) -> list[Path]:
    if not workspaces_dir.exists():
        return []
    return sorted(
        p for p in workspaces_dir.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and (p / "inbox").is_dir())


def _msg_display_time(date_str: str) -> str:
    # "2026-09-03 10:00:00 +0800" -> "09-03 10:00"
    try:
        dt = datetime.strptime(date_str[:19], "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%m-%d %H:%M")
    except ValueError:
        return date_str


def _to_str(to_val) -> str:
    if isinstance(to_val, list):
        return ",".join(str(t) for t in to_val)
    return str(to_val) if to_val else ""


def scan_messages(workspaces_dir: Path) -> list[dict]:
    """扫全部 inbox 文件 → 每项 {file,user,from,to,date,subject,type,ref,raw?}。"""
    out = []
    for ud in _users(workspaces_dir):
        inbox = ud / "inbox"
        for f in sorted(inbox.glob("*.md")):
            msg = parse_message(f.read_text(encoding="utf-8"))
            if "raw" in msg:
                out.append({"file": f.name, "user": ud.name, "raw": msg["raw"]})
                continue
            out.append({
                "file": f.name,
                "user": ud.name,
                "from": str(msg.get("from", "")),
                "to": msg.get("to", []),
                "date": str(msg.get("date", "")),
                "subject": str(msg.get("subject", "")),
                "type": str(msg.get("type", "邮件")),
                "ref": str(msg.get("ref", "")) or None,
            })
    return out


def scan_tasks(workspaces_dir: Path) -> list[dict]:
    """扫全部 task.yaml → 每项 {dir,user,task,from,status,blocked_by,updated}。坏 yaml 字段留空。"""
    out = []
    if not workspaces_dir.exists():
        return out
    for ud in sorted(workspaces_dir.iterdir()):
        if not ud.is_dir() or ud.name.startswith(".") or not (ud / "tasks").is_dir():
            continue
        for tdir in sorted((ud / "tasks").iterdir()):
            f = tdir / "task.yaml"
            if not f.is_file():
                continue
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                data = {}
            if not isinstance(data, dict):
                data = {}
            out.append({
                "dir": tdir.name,
                "user": ud.name,
                "task": str(data.get("task") or tdir.name),
                "from": str(data.get("from") or ""),
                "status": str(data.get("status") or ""),
                "blocked_by": str(data.get("blocked_by") or ""),
                "updated": str(data.get("updated") or ""),
            })
    return out


def render_ledger(messages: list[dict]) -> str:
    """单个用户的通知台账 Markdown。入参为该用户收件的消息列表，按时间倒序渲染。"""
    ordered = sorted(messages, key=lambda m: m.get("date", ""), reverse=True)
    if not ordered:
        return "暂无往来记录\n"
    lines = ["|时间|发件人|类型|标题|ref 链路|", "|----|------|----|----|--------|"]
    for m in ordered:
        ref = f"↩ {m['ref']}" if m.get("ref") else ""
        lines.append(f"|{_msg_display_time(m['date'])}|{m['from']}|{m['type']}|{m['subject']}|{ref}|")
    return "\n".join(lines) + "\n"


def render_task_board(tasks: list[dict]) -> str:
    """全员任务看板：按五态分列。"""
    buckets: dict[str, list[dict]] = {s: [] for s in TASK_STATUSES}
    for t in tasks:
        status = t["status"] if t["status"] in TASK_STATUSES else "未开始"
        buckets[status].append(t)
    lines = []
    for s in TASK_STATUSES:
        lines.append(f"## {s}")
        items = buckets[s]
        if not items:
            lines.append("_空_\n")
            continue
        for t in items:
            blocked = f"（blocked_by: {t['blocked_by']}）" if t["status"] == "阻塞" and t["blocked_by"] else ""
            lines.append(f"- {t['task']} · @{t['user']} · from: {t['from'] or '无'} · {t['updated']} {blocked}")
        lines.append("")
    return "\n".join(lines)


PAGE_SIZE = 10          # 消息审计每页条数（与前端分页粒度一致）


def _msg_items(messages: list[dict]) -> list[dict]:
    """frontmatter 列表 → 前端展示项列表：去重 + 转展示字段，按文件名(时间戳)倒序，最新在前。

    - 同名副本：同一封信群发多人时各收件人 inbox 是同名文件，只留一份；
    - 坏 frontmatter：不抛，跳过也跳过统计（无元数据可展示）。
    """
    seen_files: set[str] = set()
    items = []
    for m in sorted(messages, key=lambda x: x["file"], reverse=True):
        if "raw" in m or m["file"] in seen_files:
            continue
        seen_files.add(m["file"])
        item = {
            "id": m["file"].removesuffix(".md"),
            "type": m["type"],
            "time": _msg_display_time(m["date"]),
            "from": m["from"],
            "to": _to_str(m["to"]),
            "subject": m["subject"],
        }
        if m.get("ref"):
            item["ref"] = m["ref"]
        items.append(item)
    return items


def _msg_stats(items: list[dict]) -> dict:
    """从展示项预聚合的统计头部（不受分页位置影响）。"""
    counts = {"total": len(items), "邮件": 0, "协同单": 0, "回执": 0, "退回": 0}
    for it in items:
        t = it.get("type", "邮件")
        if t in ("协同单", "回执", "退回", "邮件"):
            counts[t] += 1
    return counts


def _msg_ranking(messages: list[dict]) -> list[dict]:
    """收发合计活跃度排行 top6（返回 [{name,n},...] 按 n 降序）。"""
    tally: dict[str, int] = {}
    for m in messages:
        if "raw" in m:
            continue
        tally[m["from"]] = tally.get(m["from"], 0) + 1
        to_val = m["to"] if isinstance(m["to"], list) else [m["to"]]
        for t in to_val:
            if t and "所有" not in str(t):
                tally[str(t)] = tally.get(str(t), 0) + 1
    top = sorted(tally.items(), key=lambda x: (-x[1], x[0]))[:6]
    return [{"name": name, "n": n} for name, n in top]


def split_msgs_pages(messages: list[dict], page_size: int = PAGE_SIZE) -> list[list[dict]]:
    """把消息展示项切成固定大小页（时间倒序，最新在前）。每页是展示字段合法的列表。"""
    items = _msg_items(messages)
    return [items[i:i + page_size] for i in range(0, len(items), page_size)]


def build_data_json(messages: list[dict], tasks: list[dict], generated_at: str) -> dict:
    """组装 site/app.js 的 data.json「页面元头」契约（页面渲染层已定死，勿改键名）。

    消息不再内嵌——改为页元头：total_messages / page_size / page_count；
    统计头部由 derive 全量预聚合，保证概览视图不依赖已加载页数；任务照旧嵌入。
    """
    items = _msg_items(messages)
    pages = split_msgs_pages(messages)
    total = len(items)

    tasks_out = []
    for t in tasks:
        item = {
            "id": t["dir"],
            "title": t["task"],
            "owner": t["user"],
            "state": TASK_STATUS_TO_STATE.get(t["status"], "todo"),
            "updated_at": t["updated"],
        }
        if t["status"] == "阻塞" and t["blocked_by"]:
            item["blocked_by"] = t["blocked_by"]
        if t["from"] and t["from"] != "无":
            item["ref"] = t["from"]
        tasks_out.append(item)

    return {
        "generated_at": generated_at,
        "total_messages": total,
        "page_size": PAGE_SIZE,
        "page_count": len(pages),
        "msg_stats": _msg_stats(items),
        "msg_ranking": _msg_ranking(messages),
        "tasks": tasks_out,
    }


# ---------- CLI ----------

def cmd_render(args: argparse.Namespace) -> None:
    ws = Path(args.workspaces).resolve()
    msgs = scan_messages(ws)
    tasks = scan_tasks(ws)

    if args.board_dir:
        board = Path(args.board_dir).resolve()
        board.mkdir(parents=True, exist_ok=True)
        for user in sorted({m["user"] for m in msgs}):
            user_msgs = [m for m in msgs if m["user"] == user and "raw" not in m]
            (board / "ledger").mkdir(parents=True, exist_ok=True)
            (board / "ledger" / f"{user}.md").write_text(
                f"# {user} 的通知台账\n\n" + render_ledger(user_msgs), encoding="utf-8")
        (board / "task-board.md").write_text(
            "# 全员任务看板\n\n" + render_task_board(tasks), encoding="utf-8")
        print(f"[derive] 已生成 board/ledger/*.md 与 board/task-board.md")

    if args.data_json:
        data_path = Path(args.data_json)
        data_path.parent.mkdir(parents=True, exist_ok=True)
        payload = build_data_json(msgs, tasks, datetime.now().astimezone().isoformat())
        data_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"[derive] 已生成 {args.data_json}")

        # 消息分页文件:与 data.json 同级的 messages/0001.json ... (前端按需逐页拉取)
        pages = split_msgs_pages(msgs)
        pages_dir = data_path.parent / "messages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        for i, page in enumerate(pages, start=1):
            (pages_dir / f"{i:04d}.json").write_text(
                json.dumps(page, ensure_ascii=False, indent=2), encoding="utf-8")
        # 清理多余旧分页文件（保持目录与当次构建一致）
        for stale in pages_dir.glob("*.json"):
            try:
                n = int(stale.stem)
            except ValueError:
                continue
            if n > len(pages):
                stale.unlink()
        print(f"[derive] 已生成 messages/ 分页 {len(pages)} 页")


def main() -> None:
    parser = argparse.ArgumentParser(prog="derive.py", description="派生渲染引擎")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="聚合渲染 board/ 与 data.json")
    p_render.add_argument("--workspaces", required=True, help="workspaces 目录路径")
    p_render.add_argument("--board-dir", help="board/ 派生区输出目录(不传则不渲染 Markdown)")
    p_render.add_argument("--data-json", help="data.json 输出路径(不传则不输出)")

    p_lint = sub.add_parser("lint", help="CI lint(见 Task 6)")
    p_lint.add_argument("--base", help="起始 rev(默认 HEAD)")
    p_lint.add_argument("--head", help="结束 rev(默认 HEAD)")
    p_lint.add_argument("--repo-root", help="仓库根(默认取 sync.REPO_ROOT)")

    args = parser.parse_args()
    if args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "lint":
        from derive_lint import cmd_lint  # Task 6 创建
        cmd_lint(args)


if __name__ == "__main__":
    main()
