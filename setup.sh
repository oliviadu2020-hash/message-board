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

# 4. hook configs
cd "$REPO_DIR"

# Claude Code .claude/settings.json
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

- Send a message: `cd message-board && uv run sync.py --send --to <user> --from '"$NAME"' --subject "<subject>" --content "<text>"`
- Agent sessions automatically check for new mail via SessionStart hook
- Messages live in `message-board/messages/<recipient>/`
AGENTS

echo "Setup complete in $BOARD_DIR"
echo "Claude Code: .claude/settings.json"
echo "Codex: .codex/hooks.json"
