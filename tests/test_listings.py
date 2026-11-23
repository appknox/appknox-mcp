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


# --- Directory policy: descriptions describe, they don't steer -----------------
# Claude's connector review rejects descriptions that tell the model how to
# behave; Google Connected Apps also bans referencing or setting rules for
# other tools. Workflow guidance belongs in prompts.py / the Claude plugin.

import re

from appknox_mcp import remote_upload

_STEERING = re.compile(
    r"\b(never|always|do not|don't|must|should|make sure|call this|present|"
    r"instruction|instructions)\b|/appknox:",
    re.IGNORECASE,
)


async def test_tool_descriptions_do_not_steer_the_model():
    for tool in await mcp.list_tools():
        hit = _STEERING.search(tool.description or "")
        assert hit is None, f"{tool.name}: steering phrase {hit.group(0)!r}"


async def test_tool_descriptions_do_not_reference_other_tools():
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    for tool in tools:
        others = {n for n in names - {tool.name} if n in (tool.description or "")}
        assert not others, f"{tool.name} references {sorted(others)}"


def test_remote_upload_description_passes_the_same_policy():
    doc = remote_upload.remote_upload_binary.__doc__ or ""
    hit = _STEERING.search(doc)
    assert hit is None, f"remote upload_binary: steering phrase {hit.group(0)!r}"
    assert len(doc) <= 800


async def test_tool_descriptions_are_concise():
    for tool in await mcp.list_tools():
        assert len(tool.description or "") <= 800, tool.name
