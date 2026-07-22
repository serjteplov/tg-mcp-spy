# Project: telegram mcp spy

## Working conventions
- Prefer small, focused changes.
- Keep implementation simple and explicit.
- Ask before introducing new dependencies or changing project structure.
- Do not modify `.env`.
- Never commit secrets.

## Code style
- Use Python 3.13 syntax.
- Add type hints to new or changed functions.
- Prefer clear names over clever code.
- Keep functions small and single-purpose.
- Prefer standard library unless an external package is justified.

## Testing
- Add or update tests for behavior changes.
- Keep tests deterministic and fast.
- Put tests in `tests/`.
- Start with unit tests before broader integration coverage.
- Run `make check` only at the explicit final verification stage.
- For one changed test/module, run exactly: `uv run pytest <target-file-or-nodeid> -q --tb=short`

## Behavior expectations
When working on a task:
- Understand the goal first.
- Summarize what changed and any remaining risks.

## Context discipline
Maintain a working set of files already inspected in this session.
- Do not reread an unchanged file.
- Prefer line ranges, Grep, and targeted symbols over full-file reads.
- If the required file is not in the agreed allowlist, stop and ask permission.

## Output discipline
- Do not print source code, diffs, file contents, or raw tool output in chat.
- After an edit, report only: file path, purpose, and changed-line count.
- After a command, report only: command, pass/fail, and final summary line.
- Use `git diff --stat` instead of `git diff`.

## OpenSpec Integration
This project uses OpenSpec for spec-driven development. `openspec/specs/`
is the single source of truth for current system behavior. `openspec/changes/`
holds in-progress and archived feature proposals.
Never edit files under `openspec/specs/` directly — only via delta specs merged during archive.

