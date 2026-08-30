"""sync.py - message board sync engine (send + check)"""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys
import typing as t
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


def _git(repo_dir: Path, cmd: t.List[str], quiet: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(["git"] + cmd, cwd=repo_dir, capture_output=True, text=True)
    return result


def _safe_pull(repo_dir: Path, max_retries: int = 3) -> None:
    """git pull --rebase + pull 失败时继续亦校验 rebase 冲突
    若 rebase 中断策略回退则需手动干预（total abort）
    Returns after attempt (either success or possible rebase in progress).
    """
    for attempt in range(max_retries):
        _git(repo_dir, ["fetch", "origin", "--quiet"])
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            return
        branch = result.stdout.strip()
        result = _git(repo_dir, ["pull", "origin", branch, "--rebase", "--quiet"])
        if result.returncode == 0:
            return  # success

        # pull fails: may be rebase conflict, may be fetch-time push
        if "cannot pull with rebase" in result.stderr:
            # rebase conflict: try continues as-is (merge fails as-is, manual resolve)
            # In this app conflict should never happen (messages are new files),
            # so we log warning and let check continue.
            print(f"warn: rebase conflict: {result.stderr.strip()}", file=sys.stderr)
            return
        # fetch-time race (pushed while we were fetching): retry next attempt
        if attempt < max_retries - 1:
            continue
        print(f"warn: git pull skipped: {result.stderr.strip()}", file=sys.stderr)


def send(args):
    """Write message to workspaces/<to>/inbox/ then git add/commit/push
    Returns 0 on success"""
    repo = Path(args.repo).resolve()
    workspaces_dir = repo / "workspaces"
    if not workspaces_dir.exists():
        print(f"Error: workspaces not found: {workspaces_dir}", file=sys.stderr)
        return 1

    to_dir = workspaces_dir / args.to
    inbox_dir = to_dir / "inbox"
    if not inbox_dir.exists():
        inbox_dir.mkdir(parents=True)

    filename = generate_filename(args.from_user, args.subject)
    filepath = inbox_dir / filename

    # content: --content or --file
    if args.file:
        content = Path(args.file).read_text()
    else:
        content = args.content or ""

    frontmatter = build_frontmatter(args.from_user, args.to, args.subject)
    filepath.write_text(frontmatter + content)

    # git pull --rebase (sync with remote first)
    _safe_pull(repo)

    # git add/commit
    rel_inbox = f"workspaces/{args.to}/inbox/{filename}"
    _git(repo, ["add", rel_inbox])
    result = _git(repo, ["commit", "-m", f"msg: {args.subject}"])
    if result.returncode != 0 and "nothing to commit" not in result.stderr:
        raise RuntimeError(f"git commit failed: {result.stderr}")

    # git push with retry (someone may have pushed while we were committing)
    max_retries = 3
    for attempt in range(max_retries):
        result = _git(repo, ["push"])
        if result.returncode == 0:
            print(f"Sent: {filepath}")
            return 0
        # push failed: pull --rebase then retry
        if attempt < max_retries - 1:
            _safe_pull(repo)
            if _has_rebase_pending(repo):
                return 1
            continue
        raise RuntimeError(f"git push failed after {max_retries} attempts: {result.stderr}")


def check(args):
    """Check for new mail in workspaces/<user>/inbox/
    Returns 0 = new mail (notified), 1 = no mail, 2 = error"""
    repo = Path(args.repo).resolve()
    inbox_dir = repo / "workspaces" / args.user / "inbox"
    if not inbox_dir.exists():
        print(f"Error: inbox dir not found: {inbox_dir}", file=sys.stderr)
        return 2

    # git pull --rebase (offline ok)
    _safe_pull(repo)

    # Get current file list
    files = sorted([f.name for f in inbox_dir.iterdir() if f.is_file()])
    if not files:
        return 1

    # Load seen list
    seen_path = repo / "workspaces" / args.user / ".sync_seen"
    seen = set()
    if seen_path.exists():
        seen = set(seen_path.read_text().strip().splitlines())

    # New files
    new_files = [f for f in files if f not in seen]

    # Save state
    seen_path.write_text("\n".join(files) + "\n")

    if new_files:
        for fname in new_files[:3]:
            filepath = inbox_dir / fname
            text = filepath.read_text()
            subject = extract_subject(text)
            print(f"📬 New mail from {extract_sender(text)}: {subject}")
        return 0
    return 1


def _has_rebase_pending(repo_dir: Path) -> bool:
    """True when a rebase is currently in progress (incomplete)"""
    result = subprocess.run(
        ["git", "rebase", "--show-current-patch"],
        cwd=repo_dir, capture_output=True, text=True
    )
    # returncode 0 means rebase is in progress (has patch to apply)
    if result.returncode != 0:
        return False
    # Also verify by output: actual patch content means rebase is stuck
    return bool(result.stdout.strip())


def extract_sender(text: str) -> str:
    if text.startswith("---\n"):
        try:
            fm = text.split("---\n")[1].split("---\n")[0]
            data = yaml.safe_load(fm)
            return data.get("from", "unknown")
        except Exception:
            pass
    return "unknown"


def extract_subject(text: str) -> str:
    if text.startswith("---\n"):
        try:
            fm = text.split("---\n")[1].split("---\n")[0]
            data = yaml.safe_load(fm)
            return data.get("subject", "(no subject)")
        except Exception:
            pass
    return "(no subject)"


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


if __name__ == "__main__":
    sys.exit(main())
