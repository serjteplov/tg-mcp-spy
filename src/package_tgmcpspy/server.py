"""FastMCP demo server for tg-mcp-spy."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tg-mcp-spy", json_response=True, debug=True)


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.resource("greeting://{name}")
def greeting(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"


@mcp.prompt()
def greet_user(name: str, style: str = "friendly") -> str:
    """Prompt the user for their name and greet them."""
    if style == "formal":
        return f"Good day, {name}. Welcome to the FastMCP demo."
    return f"Hello, {name}! Welcome to the FastMCP demo."


def main() -> None:
    """Run the MCP server with uvicorn."""
    import uvicorn

    uvicorn.run(
        "package_tgmcpspy.server:mcp",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
