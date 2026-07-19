#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty')"

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

BLOCK_PATTERNS=(
  '(^|[[:space:]])rm[[:space:]]+-rf([[:space:]]|$)'
  '(^|[[:space:]])sudo[[:space:]]+rm([[:space:]]|$)'
  '(^|[[:space:]])dropdb([[:space:]]|$)'
  'DROP[[:space:]]+DATABASE'
  'db:reset'
  'terraform[[:space:]]+destroy'
  'kubectl[[:space:]]+delete'
  'docker[[:space:]]+system[[:space:]]+prune'
  'git[[:space:]]+push[[:space:]].*--force'
  'delete-bucket'
  '(^|[[:space:]])cat[[:space:]].*\.env([[:space:]]|$)'
  '(^|[[:space:]])less[[:space:]].*\.env([[:space:]]|$)'
  '(^|[[:space:]])grep[[:space:]].*\.env([[:space:]]|$)'
  '(^|[[:space:]])cp[[:space:]].*\.pem([[:space:]]|$)'
)

for pattern in "${BLOCK_PATTERNS[@]}"; do
  if printf '%s' "$COMMAND" | grep -Eq "$pattern"; then
    echo "Blocked dangerous Bash command: $COMMAND" >&2
    exit 2
  fi
done

exit 0
