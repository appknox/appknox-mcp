"""Marketplace-readiness checks: annotations every directory requires, and
listing manifests kept in step with the package version."""

import subprocess
import sys
from pathlib import Path

from appknox_mcp import server  # noqa: F401  (registers every tool)
from appknox_mcp.app import mcp

ROOT = Path(__file__).resolve().parent.parent


async def test_every_tool_has_title_and_safety_hint():
    tools = await mcp.list_tools()
    assert tools
    for tool in tools:
        assert tool.title, f"{tool.name} has no title"
        hints = tool.annotations
        assert hints is not None, f"{tool.name} has no annotations"
        # Claude's connector directory: readOnlyHint true OR destructiveHint true.
        assert hints.readOnlyHint or hints.destructiveHint, tool.name
        assert len(tool.name) <= 64


async def test_only_upload_writes():
    writers = {t.name for t in await mcp.list_tools() if not t.annotations.readOnlyHint}
    assert writers == {"upload_binary"}


def test_listing_manifests_match_package_version():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "sync_version.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def test_readme_carries_mcp_registry_ownership_marker():
    assert "mcp-name: io.github.appknox/appknox-mcp" in (ROOT / "README.md").read_text()
