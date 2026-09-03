"""Smoke tests: the package imports and the server entry point is wired."""

import sys

from appknox_mcp import app, server
from appknox_mcp.instructions import WORKFLOW_INSTRUCTIONS


def test_main_is_callable():
    assert callable(server.main)


def test_mcp_instance_exists():
    assert app.mcp is not None


def test_workflow_instructions_present():
    assert "fix-and-verify" in WORKFLOW_INSTRUCTIONS.lower()


def test_install_guide_prints_install_md(capsys):
    server._print_install_guide()
    out = capsys.readouterr().out
    assert "Installing the Appknox MCP server" in out


def test_main_install_guide_flag_exits_without_starting_server(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["appknox-mcp", "--install-guide"])
    monkeypatch.setattr(server.mcp, "run", lambda **_: (_ for _ in ()).throw(AssertionError("server should not start")))
    server.main()
    assert "Installing the Appknox MCP server" in capsys.readouterr().out
