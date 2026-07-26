# Spec: MCP completion

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines MCP Completion for the resource template arguments, the
digest prompt arguments, and the dependent `post_id` argument on the
single-post resource template. Completion runs entirely against the local
cache and never contacts Telegram.

## Requirements

- **R1** The server SHALL implement MCP Completion for `channel` arguments on the single-post resource template, both channel-post list templates, and the canonical digest prompt.
- **R2** Channel completion candidates SHALL come only from tracked conversations, use username when present and otherwise decimal Telegram ID, be deduplicated, prefix-matched deterministically, and be capped at 100 values.
- **R3** For `post://{channel}/{post_id}`, the server SHALL complete `post_id` from the locally cached channel supplied in the Completion argument context. It SHALL return string forms of at most the newest 100 matching Telegram message IDs, newest first, and SHALL apply the typed post-ID prefix.
- **R4** Completion for the digest prompt's `channels` argument SHALL preserve all text through the final space, complete only the active segment, and omit canonical channels already selected earlier in the same argument.
- **R5** The server SHALL NOT provide Completion candidates for `days`, `start_date`, or `end_date` on resources or prompts.

## Scenarios

### Channel completion

#### S1 — Complete username and numeric fallback

```
GIVEN tracked conversation A has username "alpha"
  AND tracked conversation B has no username and Telegram ID 200
  AND cached conversation C is not tracked
WHEN the client requests channel Completion with an empty prefix
THEN the values include "alpha" and "200"
  AND they do not include A's duplicate numeric alias
  AND they do not include C
```

#### S2 — Filter channel Completion by prefix

```
GIVEN tracked usernames "alpha", "alpine", and "beta"
WHEN the client requests channel Completion for "al"
THEN the values include "alpha" and "alpine"
  AND they exclude "beta"
```

### Post-id completion

#### S3 — Complete newest post IDs for a selected channel

```
GIVEN tracked conversation A has more than 100 cached posts
  AND the Completion context selects A
WHEN the client requests post_id Completion with an empty prefix
THEN at most 100 values are returned
  AND they are A's newest cached Telegram message IDs
  AND they are ordered newest first
```

#### S4 — Missing dependent context returns no candidates

```
GIVEN the Completion request does not provide a channel
WHEN the client requests post_id Completion
THEN the server returns an empty Completion value list
  AND it does not contact Telegram
```

#### S5 — Unknown dependent channel returns no candidates

```
GIVEN the Completion context names a channel absent from the local cache
WHEN the client requests post_id Completion
THEN the server returns an empty Completion value list
  AND it does not raise a Telegram resolution error
```

### Digest channel completion

#### S6 — Complete the next digest channel

```
GIVEN tracked canonical channels "alpha", "beta", and "gamma"
WHEN the client requests channels Completion for "alpha b"
THEN the values preserve "alpha " and suggest "alpha beta"
  AND they do not suggest "alpha alpha"
```

### Temporal arguments

#### S7 — Request temporal Completion

```
WHEN a client requests Completion for days, start_date, or end_date
THEN the server returns no custom temporal suggestions
```