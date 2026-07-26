# Spec: Telegram session and credentials

## Status

LIVE — implemented, reviewed, and verified.

## Scope

This spec defines how the `tg-mcp-spy` MCP server connects to Telegram:
required environment variables, the Telethon session used, and retry
behavior for rate-limited Telegram calls.

## Requirements

- **R1** The server SHALL read Telegram credentials from environment variables: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION_STRING`.
- **R2** The server SHALL use Telethon with a `StringSession` to connect as a Telegram user.
- **R3** The server SHALL fail fast on startup if the session is not authorized.
- **R4** The server SHALL retry on `FloodWaitError` up to 3 times with a capped sleep.

## Scenarios

### S1 — Unauthorized session

```
GIVEN the configured Telegram session string is invalid or expired
WHEN the server starts or connects
THEN startup fails with a clear authorization error
```

### S2 — Flood wait handling

```
GIVEN a Telegram call raises FloodWaitError with 5 seconds
WHEN the server retries the call
THEN it waits up to the requested time and succeeds within 3 retries
```