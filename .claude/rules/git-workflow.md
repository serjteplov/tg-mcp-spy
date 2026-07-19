---
paths:
  - "**/*"
---

# Git Workflow Rules

## Commit hygiene
- Keep changes small and reviewable.
- Do not mix refactoring with feature work unless necessary.
- Avoid touching unrelated files.

## Branch naming
- Use prefixes: `feature/`, `fix/`, `refactor/`, `docs/`, `chore/`.
- Example: `feature/add-user-authentication`, `fix/resolve-race-condition`.

## Commit messages
- Use imperative mood ("Add feature", not "Added feature" or "Adding feature").
- Keep the subject line ≤72 characters.
- Reference issue IDs when applicable (`Closes #123`).
- Leave a blank line between subject and body if a body is needed.

## Before commit
Run:
```bash
make check
```

## Rebase and merge
- Prefer rebase for local feature branches before merging.
- Merge only for long-lived integration branches.
- Avoid force-pushing to shared branches.

## Safety
- Never commit `.env`, secrets, tokens, or credentials.
- Ask before destructive actions, force-push, history rewrites, or deleting branches.
- Ask before changing CI, release flow, or dependency strategy.

## Review mindset
- Summarize changed files.
- Note risks and follow-ups.
- Mention which checks were run.
