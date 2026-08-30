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
    print("check not implemented")
    return 1

if __name__ == "__main__":
    sys.exit(main())
