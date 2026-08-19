"""Entry point for the Appknox KnoxIQ stdio MCP server."""

import sys

from appknox_mcp.app import access_token, mcp

# Tool modules register their @mcp.tool tools on import.
from appknox_mcp import findings, resolve, status  # noqa: E402, F401


def main() -> None:
    """Run the stdio MCP server.

    A missing token warns rather than exits: exiting mid-handshake surfaces to
    clients as an opaque connection error, so instead the tools appear and each
    call fails with a clear auth error until the token is set.
    """
    if not access_token:
        print(
            "Warning: APPKNOX_ACCESS_TOKEN is not set — tool calls will fail with an "
            "auth error until it is configured (format <Access Key ID>:<Secret>).",
            file=sys.stderr,
        )
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
