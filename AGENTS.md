# Message Board Collaboration Guide

For AI agents (Claude Code, Codex, etc.) collaborating in this workspace.

---

## Build Rules

- **NO** manual file creation / update / deletion in anyone else's `workspaces/<u>/inbox/` — all writes MUST go through `scripts/sync.py`.
- Your own `workspaces/<me>/` (outside inbox) is private; do not touch others'.
- `workspaces/share/` is free-for-all.
- Message format: Markdown with YAML frontmatter.
- Git operations must flow through sync.py (no manual `git add/commit/push` for message files).

## Send a Message

```bash
cd message-board

# Write content inline
uv run scripts/sync.py --send --to <user> --from <me> \
    --subject "<subject>" --content "<text>"

# Or from a file
uv run scripts/sync.py --send --to <user> --from <me> \
    --subject "<subject>" --file ./note.md
```

- `--to <user>`: The recipient folder under `workspaces/`
- `--from <me>`: Your username
- Creates `workspaces/<to>/inbox/<date>-<from>-<slug>.md` and git pushes

## Agent Start Hook

When session starts, check for new messages:

```bash
uv run scripts/sync.py --check --user <me>
```

- Exit 0 + stdout text = new mail → read and notify user
- Exit 1 = no new mail
- Exit 2 = error

Hook config in `.claude/settings.json` and `.codex/hooks.json` handles this automatically.

## Join This Collaboration

```bash
./scripts/setup.sh --name <yourname>
uv sync
# creates workspaces/<yourname>/inbox/
```

Then commit `workspaces/<yourname>/` (folder) and update `.claude/settings.json` & `.codex/hooks.json` with your command.

## Read New Messages Manually

```bash
cd message-board
uv run scripts/sync.py --check --user <me>
# prints: 📬 New mail from <from>: <subject>
```

Then read the file directly: `cat workspaces/<me>/inbox/<file>`

## Example: Alice sends Bob a note

```bash
# Alice's shell
cd message-board
uv run scripts/sync.py --send --to bob --from alice \
    --subject "issue-42 fix ready" \
    --content "the fix is in the branch, please review"

# Bob receives (via hook or manual check)
cd message-board
uv run scripts/sync.py --check --user bob
# Output: 📬 New mail from alice: issue-42 fix ready
```
