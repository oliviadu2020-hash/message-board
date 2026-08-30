"""sync.py - message board sync engine"""
import argparse
from datetime import datetime, timezone
import re
import subprocess
import sys

import yaml


def build_frontmatter(from_user: str, to: str, subject: str) -> str:
    """Build YAML frontmatter block"""
    now = datetime.now(timezone.utc).astimezone()
    data = {
        "from": from_user,
        "to": to,
        "date": now.isoformat(),
        "subject": subject,
    }
    yaml_text = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
    return f"---\n{yaml_text}---\n\n"


def generate_filename(from_user: str, subject: str) -> str:
    """Generate filename: {from_user}-{slug}.md
    slug: kebab-case of first 5 words, max 30 chars.
    Keeps CJK characters (\\w includes them), strips unsafe ASCII punctuation."""
    words = subject.lower().strip().split()
    words = words[:5]
    slug = "-".join(words)
    slug = re.sub(r'[^\w\-]', '', slug)
    slug = slug[:30]
    if not slug:
        slug = "message"
    return f"{from_user}-{slug}.md"


def main(argv=None):
    parser = argparse.ArgumentParser(description="message board sync")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--to")
    parser.add_argument("--from_user", dest="from_user")
    parser.add_argument("--subject")
    parser.add_argument("--content")
    parser.add_argument("--file")
    parser.add_argument("--user")
    parser.add_argument("--repo", default=".")
    args = parser.parse_args(argv)

    if args.send:
        return send(args)
    if args.check:
        return check(args)
    parser.print_help()
    return 1

def send(args):
    """Write message file to messages/<to>/ + git add/commit/push"""
    from pathlib import Path
    repo = Path(args.repo).resolve()
    messages_dir = repo / "messages" / args.to
    if not messages_dir.exists():
        print(f"Error: messages dir not found: {messages_dir}", file=sys.stderr)
        return 1

    filename = generate_filename(args.from_user, args.subject)
    filepath = messages_dir / filename

    # content: --content or --file
    if args.file:
        content = Path(args.file).read_text()
    else:
        content = args.content or ""

    frontmatter = build_frontmatter(args.from_user, args.to, args.subject)
    filepath.write_text(frontmatter + content)

    # git add/commit/push
    subprocess.run(
        ["git", "add", f"messages/{args.to}/{filename}"],
        cwd=repo, capture_output=True, text=True
    )
    result = subprocess.run(
        ["git", "commit", "-m", f"msg: {args.subject}"],
        cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0 and "nothing to commit" not in result.stderr:
        raise RuntimeError(f"git commit failed: {result.stderr}")
    result = subprocess.run(
        ["git", "push"],
        cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git push failed: {result.stderr}")

    print(f"Sent: {filepath}")
    return 0


def check(args):
    """Check for new mail: git pull + compare file list"""
    from pathlib import Path
    repo = Path(args.repo).resolve()
    messages_dir = repo / "messages" / args.user
    if not messages_dir.exists():
        print(f"Error: messages dir not found: {messages_dir}", file=sys.stderr)
        return 2

    # 1. git fetch + pull --rebase（网络失败则跳过，不影响 check）
    try:
        subprocess.run(
            ["git", "fetch", "origin", "--quiet"],
            cwd=repo, capture_output=True, text=True, timeout=30
        )
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo, capture_output=True, text=True
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            result = subprocess.run(
                ["git", "pull", "origin", branch, "--rebase", "--quiet"],
                cwd=repo, capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                print(f"warn: git pull skipped: {result.stderr.strip()}", file=sys.stderr)
    except Exception:
        pass  # offline / no remote → proceed anyway

    # 2. Get current file list
    files = sorted([f.name for f in messages_dir.iterdir() if f.is_file()])
    if not files:
        return 1

    # 3. Load seen list
    state_path = repo / ".sync_seen"
    seen = set()
    if state_path.exists():
        seen = set(state_path.read_text().strip().splitlines())

    # 4. New files
    new_files = [f for f in files if f not in seen]

    # 5. Save state
    state_path.write_text("\n".join(files) + "\n")

    if new_files:
        for fname in new_files[:3]:
            filepath = messages_dir / fname
            text = filepath.read_text()
            subject = extract_subject(text)
            print(f"📬 New mail from {extract_sender(text)}: {subject}")
        return 0
    return 1


def extract_sender(text: str) -> str:
    """Extract from field from YAML frontmatter"""
    if text.startswith("---\n"):
        try:
            fm = text.split("---\n")[1].split("---\n")[0]
            data = yaml.safe_load(fm)
            return data.get("from", "unknown")
        except Exception:
            pass
    return "unknown"


def extract_subject(text: str) -> str:
    """Extract subject from YAML frontmatter"""
    if text.startswith("---\n"):
        try:
            fm = text.split("---\n")[1].split("---\n")[0]
            data = yaml.safe_load(fm)
            return data.get("subject", "(no subject)")
        except Exception:
            pass
    return "(no subject)"

if __name__ == "__main__":
    sys.exit(main())
