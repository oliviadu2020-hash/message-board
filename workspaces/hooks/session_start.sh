#!/usr/bin/env bash
# workspaces/hooks/session_start.sh
# Claude/Codex SessionStart hook 的统一入口：自动查一下未读邮件
set -e

cd "$(dirname "$0")/.."  # -> <project>/workspaces
uv run scripts/sync.py check
