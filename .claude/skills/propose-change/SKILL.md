---
name: propose-change
description: This skill should be used when starting a new feature or
  change under OpenSpec, to scaffold proposal.md, design.md, and delta
  specs before any implementation begins.
---

# Propose Change

1. Create `openspec/changes/<kebab-case-feature-name>/`.
2. Write `proposal.md`: why, what changes, scope, risks.
3. Write `design.md`: technical approach, alternatives.
4. Write `specs/<domain>/spec.md` delta using ADDED/MODIFIED/REMOVED
   Requirements with Given/When/Then scenarios.
5. Write `tasks.md` as a checklist derived from design.md.
6. Stop and ask the human to review before any implementation.
