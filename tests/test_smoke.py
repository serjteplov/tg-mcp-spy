"""Smoke tests for the tg-mcp-spy MCP server."""

from package_tgmcpspy.server import add, greet_user, greeting


def test_add_returns_sum() -> None:
    assert add(2, 3) == 5


def test_greeting_includes_name() -> None:
    assert "Alice" in greeting("Alice")


def test_greet_user_friendly_includes_name() -> None:
    assert "Alice" in greet_user("Alice")


def test_greet_user_formal_includes_name() -> None:
    result = greet_user("Alice", style="formal")
    assert "Alice" in result
    assert "Good day" in result
