#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
TOOL_NAME="$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')"
FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

PROTECTED_PATTERNS=(
  ".env"
  ".env."
  "secrets"
  "credentials"
  ".pem"
  ".key"
  "id_rsa"
  "id_ed25519"
  ".p12"
  ".claude/settings.local.json"
  "CLAUDE.local.md"
)

for pattern in "${PROTECTED_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$pattern"* ]]; then
    echo "Blocked: $TOOL_NAME is not allowed for sensitive file '$FILE_PATH'" >&2
    exit 2
  fi
done

exit 0
