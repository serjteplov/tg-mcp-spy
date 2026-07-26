# Spec: MCP tool contract

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines the cross-cutting behavior that applies to every MCP tool
exposed by the server: serial processing, the absence of MCP notifications,
error reporting, and the serialization of destructive resets with update
operations.

## Requirements

- **R1** Tool calls SHALL be processed sequentially. Mutating and Telegram-I/O operations SHALL be serialized, batch resolution SHALL process identifiers one at a time, and destructive resets SHALL not overlap update operations.
- **R2** The server SHALL NOT emit MCP notifications or resource-subscription events.
- **R3** Tool errors SHALL be surfaced by raising FastMCP exceptions, not by returning `{ok, error}` envelopes.

## Scenarios

### S1 — Sequential processing

```
GIVEN two MCP clients call update_channel("A") and update_channel("B") at the same time
WHEN the server handles the calls
THEN the two updates run one after another, not in parallel
```

### S2 — No notifications

```
GIVEN update_channel("A") adds new posts to the cache
WHEN the update completes
THEN the server does not emit any MCP notification or resource-subscription event
```

### S3 — Reset and update are serialized

```
GIVEN one client requests a channel update
  AND another client requests a confirmed full reset concurrently
WHEN the server processes both calls
THEN one operation completes before the other begins
  AND they do not mutate the cache concurrently
```