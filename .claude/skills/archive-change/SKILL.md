---
name: archive-change
description: This skill should be used when a change's implementation
  is complete, reviewed, and approved, to merge its delta specs into
  the main specs and archive the change folder.
---

# Archive Change

1. Confirm all tasks in `tasks.md` are checked off and reviewer/tester
   have signed off on all scenarios.
2. Ask the human for explicit confirmation to archive.
3. Merge ADDED/MODIFIED/REMOVED requirements from
   `changes/<feature-name>/specs/` into `openspec/specs/<domain>/spec.md`.
4. Move `changes/<feature-name>/` to
   `changes/archive/YYYY-MM-DD-<feature-name>/`.
5. Confirm the merge with a short diff summary to the human.
6. Whenever significant changes are made or high-level architectural shifts, big features, or breaking changes, you must document them comprehensively in the `project.md`
