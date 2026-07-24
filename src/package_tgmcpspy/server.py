"""FastMCP server for tg-mcp-spy."""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from package_tgmcpspy.config import AppConfig, load_config
from package_tgmcpspy.db import Repository, init_schema
from package_tgmcpspy.models import (
    Channel,
    ChannelNotFoundError,
    ConfigError,
    Post,
    TelegramError,
    normalize_identifier,
)
from package_tgmcpspy.telegram import TelegramClientWrapper

type MCPContext = Context[Any, AppContext, Any]


@dataclass(frozen=True)
class AppContext:
    """Context passed through the FastMCP lifespan."""

    config: AppConfig
    repo: Repository
    client: TelegramClientWrapper
    # Serializes mutating and Telegram-I/O operations so destructive tools and
    # update calls never overlap. Each tool acquires the lock at its public
    # boundary; private helpers stay lock-free.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


# Bound by ``app_lifespan`` so tools can reach the AppContext without going
# through ``ctx.request_context``, which is broken on mcp 1.28.x (FastMCP
# swallows the underlying ``LookupError`` in ``get_context`` and hands tools
# a Context whose ``_request_context`` is ``None``).
_app_context: AppContext | None = None


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Initialize config, database, and Telegram client for the lifespan."""
    global _app_context
    config = load_config()
    # StaticPool holds a single connection for the process lifetime, matching the
    # sequential-processing design (all MCP calls run one at a time).
    engine = create_engine(
        f"sqlite:///{config.database_path}",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    init_schema(engine)
    repo = Repository(engine)
    client = TelegramClientWrapper(config)
    await client.connect()
    _app_context = AppContext(config=config, repo=repo, client=client)
    try:
        yield _app_context
    finally:
        await client.disconnect()
        engine.dispose()
        _app_context = None


mcp = FastMCP("tg-mcp-spy", lifespan=app_lifespan, json_response=True)


def _context(ctx: MCPContext) -> AppContext:
    """Return the AppContext bound by ``app_lifespan``.

    The ``ctx`` parameter is intentionally unused. On mcp 1.28.x FastMCP
    catches the ``LookupError`` from ``self._mcp_server.request_context``
    inside ``get_context()`` and hands tools a ``Context`` whose
    ``_request_context`` is ``None``, which makes every access via
    ``ctx.request_context.lifespan_context`` raise "Context is not available
    outside of a request" (reproducible on both SSE and stdio paths).
    """
    del ctx  # unused; see docstring
    if _app_context is None:
        raise RuntimeError("Server lifespan has not started.")
    return _app_context


def _channel_to_dict(channel: Channel) -> dict[str, Any]:
    result = asdict(channel)
    result["last_fetched_at"] = (
        channel.last_fetched_at.isoformat() if channel.last_fetched_at else None
    )
    return result


def _post_to_dict(post: Post) -> dict[str, Any]:
    result = asdict(post)
    result["timestamp_utc"] = post.timestamp_utc.isoformat()
    return result


def _parse_utc_datetime(value: str, *, end_of_day: bool = False) -> datetime:
    """Parse a date string as UTC. YYYY-MM-DD is treated as start/end of day."""
    cleaned = value.strip()
    if len(cleaned) == 10:
        dt = datetime.strptime(cleaned, "%Y-%m-%d").replace(tzinfo=UTC)
        if end_of_day:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        return dt

    dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _parse_date_range(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    start = _parse_utc_datetime(start_date, end_of_day=False)
    end = _parse_utc_datetime(end_date, end_of_day=True)
    return start, end


def _resolve_post_range(
    *,
    start_date: str | None,
    end_date: str | None,
    days: int | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Validate exactly one selection mode and return the inclusive UTC range.

    ``start_date``/``end_date`` form the explicit range; ``days`` forms the
    relative range. Any other combination, or none at all, raises ``ConfigError``.
    Booleans are rejected before their integer-like coercion.
    """
    explicit = (start_date is not None) or (end_date is not None)
    if isinstance(days, bool):
        raise ConfigError("`days` must be a positive integer, got bool.")
    has_days = days is not None
    if explicit and has_days:
        raise ConfigError("Provide either explicit start_date and end_date, or days, not both.")
    if has_days:
        if not isinstance(days, int) or days <= 0:
            raise ConfigError("`days` must be a positive integer.")
        current = now if now is not None else datetime.now(UTC)
        end = current
        start = current - timedelta(days=days)
        return start, end
    if start_date is None and end_date is None:
        raise ConfigError("Provide both start_date and end_date, or a positive integer `days`.")
    if start_date is None or end_date is None:
        raise ConfigError("Both start_date and end_date are required for explicit range mode.")
    return _parse_date_range(start_date, end_date)


def _parse_batch_identifiers(raw: str) -> list[str]:
    """Parse comma-separated batch input deterministically.

    Trims surrounding whitespace per segment, ignores empty segments, and
    deduplicates while preserving first-seen order. Raises ``ConfigError`` when
    no identifier remains after parsing.
    """
    seen: set[str] = set()
    result: list[str] = []
    for segment in raw.split(","):
        cleaned = segment.strip()
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    if not result:
        raise ConfigError("`channels` must contain at least one non-empty identifier.")
    return result


async def _resolve_db_channel(
    app: AppContext,
    identifier: str,
) -> Channel:
    """Resolve an identifier to a cached channel row."""
    parsed = normalize_identifier(identifier)
    channel: Channel | None = None

    if isinstance(parsed, int):
        channel = await app.repo.get_channel_by_telegram_id(parsed)
    else:
        channel = await app.repo.get_channel_by_username(parsed)

    if channel is None:
        info = await app.client.resolve_identifier(identifier.strip())
        channel = await app.repo.get_channel_by_telegram_id(info.telegram_id)

    if channel is None:
        raise ChannelNotFoundError(f"Channel not found: {identifier!r}")

    return channel


@mcp.tool()
async def list_tracked_channels(ctx: MCPContext) -> list[dict[str, Any]]:
    """List all locally tracked channels."""
    app = _context(ctx)
    channels = await app.repo.list_tracked_channels()
    return [_channel_to_dict(channel) for channel in channels]


@mcp.tool()
async def add_channel(ctx: MCPContext, channel: str) -> dict[str, Any]:
    """Add a channel to the local tracked list."""
    app = _context(ctx)
    async with app.lock:
        info = await app.client.resolve_identifier(channel)
        stored = await app.repo.upsert_channel(info, is_tracked=True)
    return _channel_to_dict(stored)


@mcp.tool()
async def add_channel_batch(ctx: MCPContext, channels: str) -> list[dict[str, Any]]:
    """Add multiple channels to the local tracked list from a comma-separated string.

    Trims surrounding whitespace, ignores empty segments, deduplicates by
    keeping the first occurrence of each identifier, and rejects input that
    has no remaining identifier. Identifiers are processed sequentially; an
    individual failure does not stop the batch. Already tracked conversations
    are reported with status ``already_tracked``. Messages are never fetched.
    """
    app = _context(ctx)
    identifiers = _parse_batch_identifiers(channels)

    results: list[dict[str, Any]] = []
    async with app.lock:
        for identifier in identifiers:
            entry: dict[str, Any] = {"identifier": identifier}
            try:
                info = await app.client.resolve_identifier(identifier)
                existing = await app.repo.get_channel_by_telegram_id(info.telegram_id)
                if existing is not None and existing.is_tracked:
                    entry["status"] = "already_tracked"
                    entry["channel"] = _channel_to_dict(existing)
                else:
                    stored = await app.repo.upsert_channel(info, is_tracked=True)
                    entry["status"] = "added"
                    entry["channel"] = _channel_to_dict(stored)
            except (ChannelNotFoundError, TelegramError, ConfigError) as exc:
                entry["status"] = "error"
                entry["error"] = str(exc)
            results.append(entry)
    return results


@mcp.tool()
async def remove_channel(ctx: MCPContext, channel: str) -> dict[str, Any]:
    """Remove a channel from the local tracked list."""
    app = _context(ctx)
    parsed = normalize_identifier(channel)

    stored: Channel | None = None
    async with app.lock:
        if isinstance(parsed, int):
            stored = await app.repo.set_tracked(parsed, False)
        else:
            existing = await app.repo.get_channel_by_username(parsed)
            if existing is not None:
                stored = await app.repo.set_tracked(existing.telegram_id, False)

        if stored is None:
            raise ChannelNotFoundError(f"Channel not tracked: {channel!r}")

    return _channel_to_dict(stored)


@mcp.tool()
async def add_channel_all(ctx: MCPContext) -> dict[str, Any]:
    """Add every Telegram dialog to the local tracked list."""
    app = _context(ctx)
    async with app.lock:
        dialogs = await app.client.get_dialogs()
        synced = []
        for info in dialogs:
            stored = await app.repo.upsert_channel(info, is_tracked=True)
            synced.append(_channel_to_dict(stored))
    return {"synced": len(synced), "channels": synced}


@mcp.tool()
async def remove_all_channels(
    ctx: MCPContext,
    confirm: bool = False,
) -> dict[str, int]:
    """Permanently remove every locally cached conversation, post, and update cursor.

    Requires ``confirm=True``; any other value raises ``ConfigError`` before
    any database or Telegram I/O. The operation is transactional and returns
    deletion counts. Telegram memberships and subscriptions are unchanged.
    """
    app = _context(ctx)
    if confirm is not True:
        raise ConfigError("remove_all_channels requires confirm=True; no data was deleted.")
    async with app.lock:
        return await app.repo.purge_all_cache()


@mcp.tool()
async def trash_all_messages(
    ctx: MCPContext,
    confirm: bool = False,
) -> dict[str, int]:
    """Trash every locally cached conversation, post, and update cursor.

    Despite the name, this clears the entire local cache — same transactional
    full-reset behavior as ``remove_all_channels``. Requires ``confirm=True``;
    any other value raises ``ConfigError`` before any database or Telegram I/O.
    """
    app = _context(ctx)
    if confirm is not True:
        raise ConfigError("trash_all_messages requires confirm=True; no data was deleted.")
    async with app.lock:
        return await app.repo.purge_all_cache()


async def _update_channel(app: AppContext, identifier: str) -> dict[str, Any]:
    """Internal helper to fetch and cache latest posts for one channel."""
    info = await app.client.resolve_identifier(identifier)
    channel = await app.repo.get_channel_by_telegram_id(info.telegram_id)
    if channel is None:
        channel = await app.repo.upsert_channel(info, is_tracked=True)

    cutoff = datetime.now(UTC) - timedelta(days=app.config.post_ttl_days)
    await app.repo.purge_old_posts_for_channel(channel.id, cutoff)

    if channel.last_message_id is None:
        since = datetime.now(UTC) - timedelta(days=app.config.backfill_days)
        messages = await app.client.fetch_messages_since(info, since)
    else:
        messages = await app.client.fetch_messages_after(info, channel.last_message_id)

    last_message_id: int | None = channel.last_message_id
    inserted = 0
    if messages:
        inserted = await app.repo.upsert_posts(channel.id, messages)
        last_message_id = max(message.telegram_message_id for message in messages)
        await app.repo.update_channel_stats(channel.id, last_message_id, datetime.now(UTC))

    return {
        "channel": identifier,
        "fetched": len(messages),
        "inserted": inserted,
        "last_message_id": last_message_id,
    }


@mcp.tool()
async def update_channel(ctx: MCPContext, channel: str) -> dict[str, Any]:
    """Fetch latest posts for a single channel."""
    app = _context(ctx)
    async with app.lock:
        return await _update_channel(app, channel)


@mcp.tool()
async def update_all_channels(ctx: MCPContext) -> dict[str, Any]:
    """Fetch latest posts for all tracked channels."""
    app = _context(ctx)
    async with app.lock:
        channels = await app.repo.list_tracked_channels()
        results: list[dict[str, Any]] = []
        errors: dict[str, str] = {}

        for channel in channels:
            identifier = channel.username if channel.username else str(channel.telegram_id)
            try:
                result = await _update_channel(app, identifier)
                results.append(result)
            except (ChannelNotFoundError, TelegramError, ConfigError) as exc:
                errors[identifier] = str(exc)

    return {"results": results, "errors": errors}


@mcp.tool()
async def get_post(ctx: MCPContext, channel: str, post_id: int) -> dict[str, Any]:
    """Get a specific cached post by channel and post id."""
    app = _context(ctx)
    db_channel = await _resolve_db_channel(app, channel)
    post = await app.repo.get_post(db_channel.id, post_id)
    if post is None:
        raise ChannelNotFoundError(f"Post {post_id} not found in {channel!r}")
    return _post_to_dict(post)


@mcp.tool()
async def list_channel_posts(
    ctx: MCPContext,
    channel: str,
    start_date: str | None = None,
    end_date: str | None = None,
    days: int | None = None,
) -> list[dict[str, Any]]:
    """List cached posts from one channel within a UTC date range.

    Provide either both ``start_date`` and ``end_date`` for an explicit range
    or ``days`` as a positive integer for an inclusive rolling UTC interval
    ending now. The two modes cannot be combined.
    """
    app = _context(ctx)
    db_channel = await _resolve_db_channel(app, channel)
    start, end = _resolve_post_range(start_date=start_date, end_date=end_date, days=days)
    posts = await app.repo.list_channel_posts(db_channel.id, start, end)
    return [_post_to_dict(post) for post in posts]


@mcp.tool()
async def list_all_posts(
    ctx: MCPContext,
    start_date: str,
    end_date: str,
) -> list[dict[str, Any]]:
    """List cached posts from all tracked channels within a UTC date range."""
    app = _context(ctx)
    start, end = _parse_date_range(start_date, end_date)
    channels = await app.repo.list_tracked_channels()

    all_posts: list[Post] = []
    for channel in channels:
        posts = await app.repo.list_channel_posts(channel.id, start, end)
        all_posts.extend(posts)

    all_posts.sort(key=lambda post: post.timestamp_utc)
    return [_post_to_dict(post) for post in all_posts]


@mcp.resource("channel://list")
def channels_resource() -> str:
    """JSON list of tracked channels."""
    # Resources without ctx cannot access the lifespan directly.
    # This returns a placeholder; the real data comes from the tools.
    return json.dumps([])


@mcp.resource("post://{channel}/{post_id}")
def post_resource(channel: str, post_id: int) -> str:
    """JSON representation of a single cached post.

    Resources without ctx cannot access the lifespan directly.
    Use the ``get_post`` tool for live data; this resource is a placeholder.
    """
    return json.dumps({"channel": channel, "post_id": post_id, "note": "use get_post tool"})


@mcp.prompt("channel_digest://{channel}")
async def channel_digest_prompt(
    ctx: MCPContext,
    channel: str,
    days: int = 7,
) -> str:
    """Return a formatted prompt summarizing recent posts from a channel.

    Args:
        channel: Telegram channel identifier (username or numeric id).
        days: Number of days of recent posts to include. Defaults to 7.
    """
    posts = await list_channel_posts(ctx, channel, days=days)
    lines = [f"{post['timestamp_utc']}: {post['text']}" for post in posts]
    return f"Recent posts from {channel}:\n\n" + "\n\n".join(lines)


def main() -> None:
    """Run the MCP server with uvicorn via the streamable-HTTP transport."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    import uvicorn

    uvicorn.run(mcp.streamable_http_app(), host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
