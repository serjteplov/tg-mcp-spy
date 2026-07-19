---
name: git-automation
description: Run local Git workflows safely (branch, commit, rebase) before pushing.
allowed-tools:
  - Read
  - Bash
---

# Git Automation

## Trigger
Routine Git operations inside the repo.

## Procedure
1. Branch: `git checkout -b <type>/<short-desc>`.
2. Stage: `git add` only intended files.
3. Commit: clear message, reference issue if any.
4. Pre-push: run `make check`.
5. Push: `git push -u origin <branch>`.

## Safety rules
- Never force-push to shared branches.
- Never commit `.env`, secrets, or build artifacts.
- Keep commits small and focused.

## Output
- Commands executed.
- Branch name and commit summary.
