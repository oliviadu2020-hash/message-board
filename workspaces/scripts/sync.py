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


def build_message(from_user: str, to_list: list[str], subject: str, body: str) -> str:
    now = datetime.now(timezone.utc).astimezone()
    date_str = now.strftime("%Y-%m-%d %H:%M:%S %z")
    fm = {
        "from": from_user,
        "to": to_list,
        "date": date_str,
        "subject": subject,
    }
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

    git_pull()

    message = build_message(from_user, to_list, subject, body)
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

    p_check = sub.add_parser("check", help="列出未读消息")
    p_check.add_argument("--fmt", choices=["markdown", "json"], default="markdown")

    args = parser.parse_args()
    if args.cmd == "read":
        cmd_read(args)
    elif args.cmd == "write":
        cmd_write(args)
    elif args.cmd == "check":
        cmd_check(args)


if __name__ == "__main__":
    main()
