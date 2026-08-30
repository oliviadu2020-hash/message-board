"""sync.py - message board sync engine"""
import argparse
from datetime import datetime, timezone
import re
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
    print("send not implemented")
    return 1

def check(args):
    print("check not implemented")
    return 1

if __name__ == "__main__":
    sys.exit(main())
