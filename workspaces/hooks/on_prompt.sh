#!/usr/bin/env bash
# 用户每发送一轮 prompt 时,Claude Code / Codex 经 UserPromptSubmit hook 触发本脚本。
# 职责:检查收件箱;若无未读静默退出;若有,以「叮咚」形式包装输出,由 hook 注入为附加上下文。

set -e
cd "$(dirname "$0")/.."   # -> <project>/workspaces

CURRENT_USER_FILE=.current_user
if [[ ! -f "$CURRENT_USER_FILE" ]] || [[ -z "$(tr -d '[:space:]' < "$CURRENT_USER_FILE")" ]]; then
  # 本机还没配置用户身份(可能尚未走 quickstart.md),不打扰主流程
  exit 0
fi

OUTPUT=$(uv run scripts/sync.py check 2>/dev/null) || true

# sync.py 约定:无未读时输出固定字符串,此时静默,不打扰主流程
if [[ -z "$OUTPUT" ]] || [[ "$OUTPUT" == "暂无未读消息" ]]; then
  exit 0
fi

cat <<EOF
叮咚,在你发起这轮调用之前,有来自其他工作区的邮件,记得提醒用户处理,摘要如下:

${OUTPUT}
EOF
