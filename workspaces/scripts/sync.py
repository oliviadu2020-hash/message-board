"""sync.py — Message Board 投递引擎

子命令：
  read [--filename X]  读信（标记已读）
  write --to A[,B] --subject S (--content C | --file F)  写信
  check [--fmt json|markdown]  查信（未读清单）

运行前提：在 <project>/workspaces 目录下运行（通过 uv run scripts/sync.py）。
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

WORKSPACES_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = WORKSPACES_DIR.parent
SEEN_FILENAME = ".sync_seen"
CURRENT_USER_FILENAME = ".current_user"
MAX_PUSH_RETRIES = 3


# ---------- 通用工具 ----------

def log(msg: str) -> None:
    print(f"[sync.py] {msg}", file=sys.stderr)


def die(msg: str, code: int = 1) -> None:
    print(f"[sync.py] 错误: {msg}", file=sys.stderr)
    sys.exit(code)


def run_git(args: list[str], capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT)] + args,
        capture_output=capture, text=True, check=check,
    )


def git_pull() -> None:
    log("git pull ...")
    result = run_git(["pull", "--ff-only"], check=False)
    if result.returncode != 0:
        # 允许非 fast-forward 时 fallback 到 rebase（新写文件不会冲突）
        log("fast-forward 失败，尝试 rebase")
        result = run_git(["pull", "--rebase"], check=False)
        if result.returncode != 0:
            die(f"git pull 失败:\n{result.stderr}")


def git_add_commit_push(paths: list[Path], message: str) -> None:
    rel = [str(p.relative_to(REPO_ROOT)) for p in paths]
    run_git(["add"] + rel)
    # 检查是否有暂存的变更需要提交
    status = run_git(["diff", "--cached", "--quiet"], check=False)
    if status.returncode == 0:
        log("无变更,跳过 commit")
        return
    run_git(["commit", "-m", message])
    for attempt in range(1, MAX_PUSH_RETRIES + 1):
        log(f"git push (尝试 {attempt}/{MAX_PUSH_RETRIES}) ...")
        result = run_git(["push"], check=False)
        if result.returncode == 0:
            return
        log("push 被拒,重新 pull 再试")
        result_pull = run_git(["pull", "--rebase"], check=False)
        if result_pull.returncode != 0:
            die(f"git pull --rebase 失败:\n{result_pull.stderr}")
    die(f"重试 {MAX_PUSH_RETRIES} 次仍无法 push,请稍后再试")


# ---------- 用户身份 / 状态 ----------

def read_current_user() -> str:
    f = WORKSPACES_DIR / CURRENT_USER_FILENAME
    if not f.exists():
        die(f"未找到 {CURRENT_USER_FILENAME},请先通过 echo '<username>' > workspaces/.current_user 写入本机用户身份")
    user = f.read_text(encoding="utf-8").strip()
    if not user:
        die(f"{CURRENT_USER_FILENAME} 内容为空,请写入当前用户名")
    return user


def load_seen(user: str) -> set[str]:
    f = WORKSPACES_DIR / user / SEEN_FILENAME
    if not f.exists():
        return set()
    return {line.strip() for line in f.read_text(encoding="utf-8").splitlines() if line.strip()}


def save_seen(user: str, seen: set[str]) -> None:
    f = WORKSPACES_DIR / user / SEEN_FILENAME
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(sorted(seen)) + ("\n" if seen else ""), encoding="utf-8")


# ---------- 消息读写 ----------

FRONTMATTER_SEP = "---"


def parse_message(text: str) -> dict:
    """解析 frontmatter + body。损坏时返回 {raw: text} 供降级处理。"""
    if not text.startswith(FRONTMATTER_SEP + "\n"):
        return {"raw": text}
    try:
        _, fm_text, body = text.split(FRONTMATTER_SEP + "\n", 2)
    except ValueError:
        return {"raw": text}
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        return {"raw": text}
    if not isinstance(fm, dict):
        return {"raw": text}
    fm["body"] = body.lstrip("\n")
    return fm


def build_message(from_user: str, to_list: list[str], subject: str, body: str,
                  mtype: str = "邮件", ref: str | None = None) -> str:
    now = datetime.now(timezone.utc).astimezone()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S %z")
    fm = {
        "from": from_user,
        "to": to_list,
        "date": date_str,
        "subject": subject,
        "type": mtype,
    }
    if ref:
        fm["ref"] = ref
    fm_text = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
    return f"{FRONTMATTER_SEP}\n{fm_text}{FRONTMATTER_SEP}\n{body.rstrip()}\n"


def message_filename(from_user: str) -> str:
    now = datetime.now(timezone.utc).astimezone()
    return now.strftime("%Y-%m-%d-%H-%M-%S-%z") + f"-{from_user}.md"


def list_inbox(user: str) -> list[Path]:
    inbox = WORKSPACES_DIR / user / "inbox"
    if not inbox.exists():
        return []
    return sorted(inbox.glob("*.md"))


# ---------- 子命令 ----------

def cmd_read(args: argparse.Namespace) -> None:
    user = read_current_user()
    git_pull()
    seen = load_seen(user)

    if args.filename:
        target = WORKSPACES_DIR / user / "inbox" / args.filename
        if not target.exists():
            die(f"消息不存在: {args.filename}")
        files = [target]
    else:
        files = [p for p in list_inbox(user) if p.name not in seen]

    if not files:
        log("没有未读消息")
        return

    for p in files:
        msg = parse_message(p.read_text(encoding="utf-8"))
        if "raw" in msg:
            print(f"\n=== {p.name} (无 frontmatter) ===\n{msg['raw']}")
        else:
            print(f"\n=== {p.name} ===")
            print(f"from: {msg.get('from', '?')}")
            to_val = msg.get("to", [])
            if isinstance(to_val, list):
                print(f"to: {', '.join(to_val)}")
            else:
                print(f"to: {to_val}")
            print(f"date: {msg.get('date', '?')}")
            print(f"subject: {msg.get('subject', '?')}\n")
            print(msg.get("body", ""))
        seen.add(p.name)

    save_seen(user, seen)
    log(f"已读 {len(files)} 封并标记")


def cmd_write(args: argparse.Namespace) -> None:
    from_user = read_current_user()

    to_list = [u.strip() for u in args.to.split(",") if u.strip()]
    if not to_list:
        die("--to 至少需要一个收件人")

    if (args.content is None) == (args.file is None):
        die("--content 与 --file 必须二选一")

    if args.content is not None:
        body = args.content
    else:
        f = Path(args.file)
        if not f.exists():
            die(f"找不到文件: {args.file}")
        body = f.read_text(encoding="utf-8")

    subject = args.subject.strip()
    if not subject:
        die("--subject 不能为空")

    # --- 公文类型与应答链校验 ---
    mtype = args.type or "邮件"
    if mtype not in ("邮件", "协同单", "回执", "退回"):
        die(f"--type 非法: {mtype},合法值为 邮件/协同单/回执/退回")
    if mtype in ("回执", "退回"):
        if not args.ref:
            die(f"--type {mtype} 必须同时传 --ref 指向原协同单文件名")
        origin = WORKSPACES_DIR / from_user / "inbox" / args.ref
        if not origin.exists():
            die(f"--ref 指向的协同单不存在: {args.ref}")

    git_pull()

    message = build_message(from_user, to_list, subject, body, mtype=mtype, ref=args.ref)
    fname = message_filename(from_user)

    written: list[Path] = []
    for to_user in to_list:
        inbox = WORKSPACES_DIR / to_user / "inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        target = inbox / fname
        target.write_text(message, encoding="utf-8")
        written.append(target)

    to_str = ",".join(to_list)
    git_add_commit_push(
        written,
        f"docs: {from_user} sends a message to {to_str}",
    )
    log(f"已发送 {len(written)} 封,文件名 {fname}")


def cmd_check(args: argparse.Namespace) -> None:
    user = read_current_user()
    git_pull()
    seen = load_seen(user)

    unread: list[dict] = []
    for p in list_inbox(user):
        if p.name in seen:
            continue
        msg = parse_message(p.read_text(encoding="utf-8"))
        if "raw" in msg:
            unread.append({"from": "?", "to": [], "date": "?", "subject": f"[无法解析] {p.name}"})
        else:
            to_val = msg.get("to", [])
            if not isinstance(to_val, list):
                to_val = [to_val]
            unread.append({
                "from": str(msg.get("from", "?")),
                "to": [str(t) for t in to_val],
                "date": str(msg.get("date", "?")),
                "subject": str(msg.get("subject", "")),
            })

    if args.fmt == "json":
        import json
        print(json.dumps(unread, ensure_ascii=False, indent=2))
        return

    if not unread:
        print("暂无未读消息")
        return

    print("|发件人|收件人|日期|标题|")
    print("|-----|-----|---|----|")
    for m in unread:
        to_str = ",".join(m["to"]) if m["to"] else "?"
        print(f"|{m['from']}|{to_str}|{m['date']}|{m['subject']}|")


# ---------- 任务管理 ----------

TASK_STATUSES = ["未开始", "进行中", "阻塞", "待确认", "已完成"]


def today_str() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def tasks_dir(user: str) -> Path:
    return WORKSPACES_DIR / user / "tasks"


def task_yaml_path(user: str, name: str) -> Path:
    return tasks_dir(user) / name / "task.yaml"


def load_task_yaml(user: str, name: str) -> dict:
    f = task_yaml_path(user, name)
    if not f.exists():
        die(f"任务不存在: {name}（先 task create 或 task list 看现状）")
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def save_task_yaml(user: str, name: str, data: dict) -> Path:
    f = task_yaml_path(user, name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return f


def cmd_task_create(args: argparse.Namespace) -> None:
    user = read_current_user()
    name = args.name.strip()
    if not name or "/" in name or name in (".", ".."):
        die("非法任务名: 不能为空、含 / 或为 . / ..")
    git_pull()
    target = task_yaml_path(user, name)
    if target.exists():
        die(f"同名任务已存在: {name}（先 task list 看现状）")
    data = {
        "task": name,
        "from": f"inbox/{args.from_file}" if args.from_file else "无",
        "status": "未开始",
        "blocked_by": "无",
        "updated": today_str(),
    }
    saved = save_task_yaml(user, name, data)
    git_add_commit_push([saved], f"docs: {user} 创建任务 {name}")


def cmd_task_update(args: argparse.Namespace) -> None:
    user = read_current_user()
    name = args.name.strip()
    if not name or "/" in name:
        die("非法任务名")
    git_pull()
    data = load_task_yaml(user, name)
    if args.status:
        if args.status not in TASK_STATUSES:
            die(f"--status 只允许五态之一: {' / '.join(TASK_STATUSES)}")
        data["status"] = args.status
        if args.status != "阻塞":
            data["blocked_by"] = "无"
    if args.blocked:
        data["blocked_by"] = args.blocked
    if args.status is None and args.blocked is None:
        die("task update 至少需要 --status 或 --blocked 之一")
    data["updated"] = today_str()
    saved = save_task_yaml(user, name, data)
    git_add_commit_push([saved], f"docs: {user} 更新任务 {name}")


def cmd_task_list(args: argparse.Namespace) -> None:
    user = read_current_user()
    git_pull()
    rows = []
    root = tasks_dir(user)
    if root.exists():
        for p in sorted(root.glob("*/task.yaml")):
            data = load_task_yaml(user, p.parent.name)
            rows.append({
                "task": data.get("task") or p.parent.name,
                "status": data.get("status") or "?",
                "blocked_by": data.get("blocked_by") or "无",
                "updated": data.get("updated") or "?",
            })
    if args.fmt == "json":
        import json
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print("|任务|状态|阻塞原因|更新日期|")
    print("|----|----|--------|--------|")
    for r in rows:
        print(f"|{r['task']}|{r['status']}|{r['blocked_by']}|{r['updated']}|")


# ---------- 入口 ----------

def main() -> None:
    parser = argparse.ArgumentParser(prog="sync.py", description="message-board 消息收发引擎")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_read = sub.add_parser("read", help="读取未读消息")
    p_read.add_argument("--filename", help="只读指定文件")

    p_write = sub.add_parser("write", help="写入新消息")
    p_write.add_argument("--to", required=True, help="收件人,逗号分隔多人")
    p_write.add_argument("--content", help="正文文本")
    p_write.add_argument("--file", help="从文件读取正文")
    p_write.add_argument("--subject", required=True, help="邮件主题")
    p_write.add_argument("--type", choices=["邮件", "协同单", "回执", "退回"],
                         default="邮件", help="公文类型: 邮件/协同单/回执/退回")
    p_write.add_argument("--ref", help="应答原协同单文件名(回执/退回必填)")

    p_check = sub.add_parser("check", help="列出未读消息")
    p_check.add_argument("--fmt", choices=["markdown", "json"], default="markdown")

    p_task = sub.add_parser("task", help="任务包管理")
    task_sub = p_task.add_subparsers(dest="task_cmd", required=True)

    p_create = task_sub.add_parser("create", help="创建任务包")
    p_create.add_argument("--name", required=True, help="任务名(即目录名)")
    p_create.add_argument("--from", dest="from_file", help="上游协同单文件名")

    p_update = task_sub.add_parser("update", help="更新任务状态")
    p_update.add_argument("--name", required=True, help="任务名")
    p_update.add_argument("--status", choices=TASK_STATUSES, help="五态之一")
    p_update.add_argument("--blocked", help="阻塞说明(等什么)")

    p_list = task_sub.add_parser("list", help="列出本人任务")
    p_list.add_argument("--fmt", choices=["markdown", "json"], default="markdown")

    args = parser.parse_args()
    if args.cmd == "read":
        cmd_read(args)
    elif args.cmd == "write":
        cmd_write(args)
    elif args.cmd == "check":
        cmd_check(args)
    elif args.cmd == "task":
        if args.task_cmd == "create":
            cmd_task_create(args)
        elif args.task_cmd == "update":
            cmd_task_update(args)
        elif args.task_cmd == "list":
            cmd_task_list(args)


if __name__ == "__main__":
    main()
