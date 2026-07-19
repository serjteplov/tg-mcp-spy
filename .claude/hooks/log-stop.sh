#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$CLAUDE_PROJECT_DIR/.ai"

INPUT="$(cat)"
SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"')"
BRANCH="$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null || echo detached)"

printf '%s | session=%s | branch=%s | event=Stop\n' \
  "$(date '+%Y-%m-%d %H:%M:%S')" \
  "$SESSION_ID" \
  "$BRANCH" \
  >> "$CLAUDE_PROJECT_DIR/.ai/session.log"
