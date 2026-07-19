---
name: start-task
description: Use when starting a new coding task, issue, bugfix, or feature in this Python repository.
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Edit
  - MultiEdit
---

# Start Task

## Step 0: Load OpenSpec Context
Before defining the task, read `openspec/project.md`, all
`openspec/specs/**/spec.md`, and list `openspec/changes/` folder names.
Summarize before asking the user for the feature description.

## Trigger
Starting a new coding task, issue, bugfix, or feature.

## Procedure
1. Read `CLAUDE.md`.
2. Read relevant files from `.claude/rules/`.
3. Read `README.md`, `pyproject.toml`, and affected source files.
4. Summarize the task in 3-6 bullets.
5. Identify risks, assumptions, and unknowns.
6. Propose a minimal implementation plan before editing.
7. Prefer the smallest working change.
8. After edits, run `make check`.

## Output
Return:
- short task summary,
- affected files,
- implementation plan,
- checks to run.
