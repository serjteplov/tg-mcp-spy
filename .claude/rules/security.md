---
paths:
  - "src/**/*.py"
---

# Security Rules

## Input
- Validate all external inputs (files, network, user data).
- Reject unexpected types early.

## Secrets
- Load sensitive values from environment variables only.
- Do not hard-code keys, tokens, or passwords in source files.

## Dangerous operations
- Avoid `eval`, `exec`, and `pickle.loads` on untrusted data.
- Use `subprocess` with explicit arguments, not `shell=True`.

## Serialization safety
- Use `json` for untrusted data.
- Use `yaml.safe_load` instead of `yaml.load`.
- Never unpickle data from untrusted sources.

## Filesystem
- Use `pathlib` over string concatenation for paths.
- Be wary of path traversal in user-supplied paths.
- Validate and sanitize user-supplied filenames before using them.
