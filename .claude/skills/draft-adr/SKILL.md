---
name: draft-adr
description: Draft an Architecture Decision Record in docs/adr/.
allowed-tools:
  - Read
  - Bash
  - Edit
  - Write
---

# Draft ADR

## Trigger
Recording a significant architecture or design decision.

## Procedure
1. Check `docs/adr/` for existing format and numbering.
2. Draft: Context, Decision, Consequences.
3. Keep it concise (under 30 lines).
4. Propose filename and ask before writing.

## Link to OpenSpec Design
If an ADR originates from an active change, reference
`openspec/changes/<feature-name>/design.md` in the ADR's context section
and note it in `openspec/adr/` with a backlink to the change folder.

## Output
- Draft ADR text.
- Proposed filename (`docs/adr/NNNN-title.md`).
- Approval request.
