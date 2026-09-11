"""Smoke tests: the package imports and the server entry point is wired."""

import json
import sys
from pathlib import Path

import pytest

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


def _no_server_start(monkeypatch):
    monkeypatch.setattr(
        server.mcp, "run", lambda **_: (_ for _ in ()).throw(AssertionError("server should not start"))
    )


def test_main_install_guide_flag_exits_without_starting_server(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["appknox-mcp", "--install-guide"])
    _no_server_start(monkeypatch)
    server.main()
    assert "Installing the Appknox MCP server" in capsys.readouterr().out


def test_main_configure_flag_writes_config_with_no_repo(monkeypatch, tmp_path: Path):
    """The whole point: this works from a bare install, no repo checkout at all."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("APPKNOX_ACCESS_TOKEN", "id:secret")
    monkeypatch.setattr(
        sys, "argv", ["appknox-mcp", "--configure", "cursor", "--base-url", "https://x.example"]
    )
    _no_server_start(monkeypatch)

    server.main()

    entry = json.loads((tmp_path / ".cursor" / "mcp.json").read_text())["mcpServers"]["appknox"]
    assert entry["command"] == "appknox-mcp"
    assert entry["env"]["APPKNOX_ACCESS_TOKEN"] == "id:secret"


def test_main_configure_flag_requires_base_url(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["appknox-mcp", "--configure", "cursor"])
    _no_server_start(monkeypatch)

    with pytest.raises(SystemExit, match="--base-url is required"):
        server.main()


def test_main_configure_flag_requires_token_env(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("APPKNOX_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(
        sys, "argv", ["appknox-mcp", "--configure", "cursor", "--base-url", "https://x.example"]
    )
    _no_server_start(monkeypatch)

    with pytest.raises(SystemExit, match="APPKNOX_ACCESS_TOKEN"):
        server.main()


def test_main_remove_client_flag_removes_entry(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = tmp_path / ".cursor" / "mcp.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"mcpServers": {"appknox": {"command": "appknox-mcp"}}}))
    monkeypatch.setattr(sys, "argv", ["appknox-mcp", "--remove-client", "cursor"])
    _no_server_start(monkeypatch)

    server.main()

    assert "appknox" not in json.loads(path.read_text())["mcpServers"]
