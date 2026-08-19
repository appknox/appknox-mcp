"""Smoke tests: the package imports and the server entry point is wired."""

from appknox_mcp import app, server
from appknox_mcp.instructions import WORKFLOW_INSTRUCTIONS


def test_main_is_callable():
    assert callable(server.main)


def test_mcp_instance_exists():
    assert app.mcp is not None


def test_workflow_instructions_present():
    assert "fix-and-verify" in WORKFLOW_INSTRUCTIONS.lower()
