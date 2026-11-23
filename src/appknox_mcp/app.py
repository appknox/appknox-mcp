"""Shared FastMCP server instance and the authenticated Appknox client."""

import os

# Set before importing fastmcp: its banner and PyPI update-check run at import,
# and the update check's blocking network call can exceed a client's stdio
# handshake timeout.
os.environ.setdefault("FASTMCP_SHOW_SERVER_BANNER", "false")
os.environ.setdefault("FASTMCP_CHECK_FOR_UPDATES", "off")

from fastmcp import FastMCP

from appknox_mcp.client import AppknoxClient
from appknox_mcp.instructions import WORKFLOW_INSTRUCTIONS

access_token = os.environ.get("APPKNOX_ACCESS_TOKEN", "")
base_url = os.environ.get("APPKNOX_BASE_URL", "") or "https://publicapi.appknox.com"

client = AppknoxClient(base_url, access_token)
mcp = FastMCP(name="Appknox KnoxIQ", instructions=WORKFLOW_INSTRUCTIONS)

# MCP tool annotations (ToolAnnotations hints). Directory listings (Claude's
# connector directory, Google Connected Apps, Glama's quality score) require
# every tool to declare a title and whether it is read-only or destructive.
# Every tool here only calls Appknox's own API (a closed domain), hence
# openWorldHint=False throughout.
READ_ONLY: dict[str, bool] = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
# Starts a scan on Appknox (consumes scan quota, creates a new build record) —
# not reversible from here, so flagged destructive for client confirmation.
STARTS_SCAN: dict[str, bool] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "idempotentHint": False,
    "openWorldHint": False,
}
