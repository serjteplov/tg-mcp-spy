#!/usr/bin/env bash
set -euo pipefail

cd "$CLAUDE_PROJECT_DIR"

BRANCH="$(git branch --show-current 2>/dev/null || echo detached)"
DIRTY="$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')"

jq -n --arg branch "$BRANCH" --arg dirty "$DIRTY" '{
  additionalContext:
    ("Git context: current branch is \"" + $branch +
     "\"; uncommitted file count is " + $dirty +
     ". Avoid direct commits to main/master unless explicitly requested.")
}'
