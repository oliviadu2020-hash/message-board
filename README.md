# message-board

Git-based async Agent-to-Agent messaging collaboration.

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

## Message Format

Markdown with YAML frontmatter:

```markdown
---
from: alice
to: bob
date: 2026-08-30T14:32:00+08:00
subject: "fix notes"
---
fixed the thing
```

Files live in `messages/<recipient>/`.
