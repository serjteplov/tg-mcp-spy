#!/usr/bin/env bash
set -euo pipefail

INPUT="$(cat)"
FILE_PATH="$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')"

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

case "$FILE_PATH" in
  *.py)
    ./.venv/bin/ruff format "$FILE_PATH"
    ./.venv/bin/ruff check --fix "$FILE_PATH"

    if [[ "$FILE_PATH" == src/* ]]; then
      ./.venv/bin/mypy src
    fi
    ;;
  pyproject.toml)
    ./.venv/bin/ruff check src tests
    ;;
  *)
    exit 0
    ;;
esac

exit 0
