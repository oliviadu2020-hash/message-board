# Message Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a git-based async message collaboration system with Python + uv

**Architecture:**
- `sync.py` CLI: send writes file + git commit+push; check pulls + detects new files
- Agent hooks (Claude `.claude/settings.json` / Codex `hooks.json`) call `uv run sync.py --check --user <name>`
- `setup.sh` bootstraps: clone repo → uv sync → hook config → AGENTS.md

**Tech Stack:** Python 3.9+, uv, PyYAML, git CLI, Claude Code hook, Codex hook
**Spec:** `docs/specs/2026-08-30-message-board-design.md`

## Global Constraints

- Python requires-python `>=3.9`
- Dependency: `pyyaml` only; tests: `pytest` (dev)
- All git ops via subprocess.run with `cwd=<repo>`
- macOS / git ≥ 2.20 / uv ≥ 0.4 / pytest CLI = `uv run pytest`
- No third-party network libraries — git CLI only

---

### Task 1: Project Scaffold

**Files:**
- Create: `message-board/pyproject.toml`
- Create: `message-board/.gitignore`
- Create: `message-board/.python-version`
- Create: `message-board/uv.lock` (generated)
- Create: `message-board/tests/test_sync.py`
- Create: `message-board/sync.py`

**Interfaces:**
- Produces: importable `sync.py` module with `main()` entrypoint

- [ ] **Step 1: Initialize uv project**

```bash
cd message-board
uv init --name message-board --pin-project
# → creates pyproject.toml, .python-version, .gitignore
```

- [ ] **Step 2: Add runtime + dev dependencies**

```bash
uv add pyyaml
uv add --dev pytest
```

- [ ] **Step 3: Create initial test**

Create `tests/test_sync.py`:
```python
def test_import():
    """sync.py module can be imported"""
    import sync
    assert True
```

- [ ] **Step 4: Create minimal sync.py**

```python
"""sync.py - message board sync engine"""
import argparse
import sys

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
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_sync.py -v
# Expected: PASS (import works)
```

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: project scaffold with uv + sync.py cli skeleton"
```

---

### Task 2: Filename Generation

**Files:**
- Create: `message-board/filename.py` (or add to sync.py if simple)
- Modify: `message-board/tests/test_sync.py`

**Interfaces:**
- Produces: `generate_filename(from_user: str, subject: str) -> str`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_sync.py`:
```python
from sync import generate_filename

def test_generate_filename_slugged():
    assert generate_filename("alice", "issue-42 fix the bug") == \
        "alice-issue-42-fix-the-bug.md"

def test_generate_filename_spaces_and_case():
    assert generate_filename("bob", "Fix Critical Security Issue!") == \
        "bob-fix-critical-security-issue.md"

def test_generate_filename_short():
    assert generate_filename("alice", "hi") == \
        "alice-hi.md"

def test_generate_filename_unicode_safe():
    assert generate_filename("alice", "修复安全问题！！！") == \
        "alice-修复安全问题.md"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
uv run pytest tests/test_sync.py::test_generate_filename_slugged -v
# Expected: FAIL (ImportError: cannot import name 'generate_filename')
```

- [ ] **Step 3: Implement generate_filename()**

Add to `sync.py`:
```python
import re
from unicodedata import normalize

def generate_filename(from_user: str, subject: str) -> str:
    """Generate filename: {from_user}-{slug}.md
    slug: kebab-case of subject words (max 5 words, 30 chars)
    All ASCII-alphanumeric plus CJK safe characters
    """
    words = subject.lower().strip().split()
    words = words[:5]
    slug = "-".join(words)
    slug = re.sub(r'[^\w\-]', '', slug)  # \w includes CJK
    slug = slug[:30]
    if not slug:
        slug = "message"
    return f"{from_user}-{slug}.md"
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_sync.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add sync.py tests/test_sync.py
git commit -m "feat: generate_filename() for message file naming"
```

---

### Task 3: Frontmatter Builder

**Files:**
- Create: `message-board/frontmatter.py` (or add to sync.py)
- Modify: `message-board/tests/test_sync.py`

**Interfaces:**
- Produces: `build_frontmatter(from_user: str, to: str, subject: str) -> str`

- [ ] **Step 1: Write failing test**

```python
from sync import build_frontmatter

def test_build_frontmatter_format():
    result = build_frontmatter("alice", "bob", "test msg")
    assert result.startswith("---\n")
    assert "from: alice\n" in result
    assert "to: bob\n" in result
    assert "subject: \"test msg\"\n" in result
    assert "date: 20" in result  # ISO format
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_sync.py::test_build_frontmatter_format -v
# Expected: FAIL
```

- [ ] **Step 3: Implement build_frontmatter()**

Add to `sync.py`:
```python
from datetime import datetime, timezone
import yaml

def build_frontmatter(from_user: str, to: str, subject: str) -> str:
    """Build YAML frontmatter block for a new message"""
    now = datetime.now(timezone.utc).astimezone()
    data = {
        "from": from_user,
        "to": to,
        "date": now.isoformat(),
        "subject": subject,
    }
    yaml_text = yaml.safe_dump(data, default_flow_style=False, allow_unicode=True)
    return f"---\n{yaml_text}---\n\n"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_sync.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add sync.py tests/test_sync.py
git commit -m "feat: build_frontmatter() for YAML header"
```

---

### Task 4: Send Command

**Files:**
- Modify: `message-board/sync.py`
- Modify: `message-board/tests/test_sync.py`

**Interfaces:**
- Consumes: `generate_filename`, `build_frontmatter`
- Produces: `send(to, from_user, subject, content, file, repo) -> int`

- [ ] **Step 1: Write failing tests**

```python
import os
import tempfile
from sync import send

class TestSend:
    def test_send_to_nonexistent_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = send(
                to="bob",
                from_user="alice",
                subject="test",
                content="hello",
                file=None,
                repo=tmpdir,
            )
            assert result == 1  # messages/bob/ doesn't exist → error
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_sync.py::TestSend::test_send_to_nonexistent_dir -v
# Expected: FAIL (messages dir not found, currently returns 0 from main())
```

- [ ] **Step 3: Implement send()**

Replace `def send(args)` in `sync.py`:
```python
import os
from pathlib import Path
import subprocess

def send(args):
    """Send: write file + git add/commit/push"""
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
    print(f"Wrote: {filepath}")

    # git add/commit/push
    result = subprocess.run(
        ["git", "add", f"messages/{args.to}/{filename}"],
        cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"git add failed: {result.stderr}", file=sys.stderr)
        return 1

    result = subprocess.run(
        ["git", "commit", "-m", f"msg: {args.subject}"],
        cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0 and "nothing to commit" not in result.stderr:
        print(f"git commit failed: {result.stderr}", file=sys.stderr)

    result = subprocess.run(
        ["git", "push"],
        cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"git push failed: {result.stderr}", file=sys.stderr)
        return 1

    print(f"Sent: messages/{args.to}/{filename}")
    return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_sync.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add sync.py tests/test_sync.py
git commit -m "feat: send() writes file + git operations"
```

---

### Task 5: Check Command

**Files:**
- Modify: `message-board/sync.py`
- Modify: `message-board/tests/test_sync.py`

**Interfaces:**
- Consumes: internal functions
- Produces: `check(user, repo) -> int`
  - 0 = new mail (prints reminder)
  - 1 = no mail
  - 2 = error (dir not found)

- [ ] **Step 1: Write failing test**

```python
import tempfile
from sync import check

class TestCheck:
    def test_check_no_messages_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = check(user="alice", repo=tmpdir)
            assert result == 2  # dir not found
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_sync.py::TestCheck::test_check_no_messages_dir -v
# Expected: FAIL
```

- [ ] **Step 3: Implement check()**

Replace `def check(args)` in `sync.py`:
```python
import os
from pathlib import Path
import subprocess
import sys
import yaml

STATE_FILE = ".sync_seen"

def check(args):
    """Check for new mail: git pull + compare file list"""
    repo = Path(args.repo).resolve()
    messages_dir = repo / "messages" / args.user
    if not messages_dir.exists():
        print(f"Error: messages dir not found: {messages_dir}", file=sys.stderr)
        return 2

    # 1. git pull --rebase
    result = subprocess.run(
        ["git", "pull", "--rebase"],
        cwd=repo, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"git pull failed: {result.stderr}", file=sys.stderr)
        return 2

    # 2. Get current file list
    files = sorted([f.name for f in messages_dir.iterdir() if f.is_file()])
    if not files:
        return 1  # empty inbox

    # 3. Load seen list
    state_path = repo / ".sync_seen"
    if state_path.exists():
        seen = set(state_path.read_text().strip().splitlines())
    else:
        seen = set()

    # 4. New files
    new_files = [f for f in files if f not in seen]

    # 5. Save state
    state_path.write_text("\n".join(files) + "\n")

    if new_files:
        for fname in new_files[:3]:  # max 3 notifications
            filepath = messages_dir / fname
            try:
                text = filepath.read_text()
                # extract subject from frontmatter
                subject = extract_subject(text)
            except:
                subject = fname
            print(f"📬 New mail from {extract_sender(text)}: {subject}")
        return 0
    return 1

def extract_sender(text: str) -> str:
    """Extract from field via yaml frontmatter"""
    if text.startswith("---\n"):
        try:
            fm = text.split("---\n")[1].split("---\n")[0]
            data = yaml.safe_load(fm)
            return data.get("from", "unknown")
        except:
            pass
    return "unknown"

def extract_subject(text: str) -> str:
    """Extract subject from frontmatter"""
    if text.startswith("---\n"):
        try:
            fm = text.split("---\n")[1].split("---\n")[0]
            data = yaml.safe_load(fm)
            return data.get("subject", "(no subject)")
        except:
            pass
    return "(no subject)"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_sync.py -v
# Expected: PASS
```

- [ ] **Step 5: Commit**

```bash
git add sync.py tests/test_sync.py
git commit -m "feat: check() pull + detect new files + state tracking"
```

---

### Task 6: Setup Script

**Files:**
- Create: `message-board/setup.sh`
- Create: `message-board/.claude/settings.json`(for testing)
- Create: `message-board/AGENTS.md`

**Interfaces:**
- Consumes: `sync.py` (via `uv run`)
- Produces: executable `setup.sh --repo <url> --name <user> [--target-dir <dir>]`

- [ ] **Step 1: Write setup.sh**

```bash
#!/bin/bash
set -e

REPO_URL=""
NAME=""
TARGET_DIR="."

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo) REPO_URL="$2"; shift 2 ;;
        --name) NAME="$2"; shift 2 ;;
        --target-dir) TARGET_DIR="$2"; shift 2 ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

[ -z "$REPO_URL" ] && echo "Error: --repo required" >&2 && exit 1
[ -z "$NAME" ] && echo "Error: --name required" >&2 && exit 1

BOARD_DIR="$TARGET_DIR/message-board"
REPO_DIR="$(cd "$TARGET_DIR" && pwd)"

# 1. clone if not exists
if [ ! -d "$BOARD_DIR" ]; then
    git clone "$REPO_URL" "$BOARD_DIR"
fi
cd "$BOARD_DIR"

# 2. uv init if not already
if [ ! -f "pyproject.toml" ]; then
    uv init --name message-board --pin-project
fi
uv sync

# 3. create inbox dir
mkdir -p "messages/$NAME"

# 3.5. add .sync_seen to gitignore (local state file)
if [ ! -f ".gitignore" ]; then
    touch .gitignore
fi
grep -q ".sync_seen" .gitignore || echo ".sync_seen" >> .gitignore

# 4. hook configs
cd "$REPO_DIR"

# Claude .claude/settings.json
mkdir -p .claude
SETTINGS='{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "cd '"$(cd "$BOARD_DIR" && pwd)"' && uv run sync.py --check --user '"$NAME"'" } ] }
    ]
  }
}'
echo "$SETTINGS" > .claude/settings.json

# Codex hooks.json
mkdir -p .codex
HOOKS='{
  "hooks": {
    "SessionStart": [
      { "type": "command", "command": "cd '"$(cd "$BOARD_DIR" && pwd)"' && uv run sync.py --check --user '"$NAME"'" }
    ]
  }
}'
echo "$HOOKS" > .codex/hooks.json

# AGENTS.md guidance
cat > AGENTS.md <<'AGENTS'
# Message Board Guidance

This project has git-based async collaboration via `message-board/`.

## Agent Guidelines

- Use `uv run message-board/sync.py --send --to <user> --from '"$NAME"' --subject "<subject>" --content "<text>"` to send a message
- Agent sessions automatically check for new mail via SessionStart hook
- Messages live in `message-board/messages/<recipient>/`
AGENTS

echo "Setup complete in $BOARD_DIR"
echo "Claude Code: .claude/settings.json"
echo "Codex: .codex/hooks.json"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x setup.sh
```

- [ ] **Step 3: Test setup.sh**

```bash
./setup.sh --repo git@github.com:you/msg.git --name alice
# verify:
# - .claude/settings.json created
# - .codex/hooks.json created
# - AGENTS.md created
# - message-board/messages/alice/ created
```

- [ ] **Step 4: Commit**

```bash
git add setup.sh .claude/settings.json .codex/hooks.json AGENTS.md
git commit -m "feat: setup.sh one-click installer + hook configs"
```

---

### Task 7: README

**Files:**
- Create: `message-board/README.md`

**Interfaces:**
- Produces: user-facing doc with install + send + check

- [ ] **Step 1: Write README.md**

```markdown
# message-board

Git-based async Agent-to-Agent messaging.

## Install

```bash
./setup.sh --repo git@github.com:you/message-board.git --name alice
```

## Usage

### Send a message

```bash
cd message-board

# from content
uv run sync.py --send --to bob --from alice \
    --subject "fix notes" --content "fixed the thing"

# from file
uv run sync.py --send --to bob --from alice \
    --subject "fix notes" --file ./notes.md
```

### Check for new mail

```bash
uv run sync.py --check --user alice
# exit 0 = new mail, 1 = no mail, 2 = error
```

## Agent Integration

- Claude Code: session starts → auto-checks and reminds
- Codex: same

See `.claude/settings.json` and `.codex/hooks.json` for hook config.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with install and usage"
```

---

## Final Validation

After all tasks, verify integration:

```bash
# fresh clone
git clone git@github.com:you/message-board.git /tmp/msg-setup-test
cd /tmp/msg-setup-test
./setup.sh --repo git@github.com:you/message-board.git --name bob

# send a message
uv run sync.py --send --to bob --from alice --subject "test" --content "hi"

# manually check (simulating hook)
uv run sync.py --check --user bob
# Expected: 📬 New mail from alice: test

# run again → no new mail
uv run sync.py --check --user bob
# Expected: (no output, exit 1)
```

---

## Task List

- [ ] Task 1: Project scaffold + CLI skeleton
- [ ] Task 2: Filename generation (generate_filename)
- [ ] Task 3: Frontmatter builder (build_frontmatter)
- [ ] Task 4: Send command
- [ ] Task 5: Check command
- [ ] Task 6: Setup script
- [ ] Task 7: README
- [ ] Final validation
