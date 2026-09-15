"""Smoke tests: the package imports and the server entry point is wired."""

import json
import subprocess
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
        server.mcp,
        "run",
        lambda **_: (_ for _ in ()).throw(AssertionError("server should not start")),
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
        sys,
        "argv",
        ["appknox-mcp", "--configure", "cursor", "--base-url", "https://x.example"],
    )
    _no_server_start(monkeypatch)

    server.main()

    entry = json.loads((tmp_path / ".cursor" / "mcp.json").read_text())["mcpServers"][
        "appknox"
    ]
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
        sys,
        "argv",
        ["appknox-mcp", "--configure", "cursor", "--base-url", "https://x.example"],
    )
    _no_server_start(monkeypatch)

    with pytest.raises(SystemExit, match="APPKNOX_ACCESS_TOKEN"):
        server.main()


def _record_run(results=None):
    """A fake subprocess.run that records every call and returns canned
    CompletedProcess results in order (default: always succeed)."""
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if results:
            return results.pop(0)
        return subprocess.CompletedProcess(args, 0, "", "")

    return calls, fake_run


def test_install_claude_plugin_registers_marketplace_and_installs(monkeypatch):
    """No repo clone, no GitHub access: extracts the bundled (or, in this
    source checkout, the repo's own) plugin files and points `claude plugin
    marketplace add` straight at that local path."""
    calls, fake_run = _record_run()
    monkeypatch.setattr(subprocess, "run", fake_run)

    server._install_claude_plugin()

    assert calls[0][:3] == ["claude", "plugin", "marketplace"]
    assert calls[0][3] == "add"
    assert calls[1] == ["claude", "plugin", "install", "appknox@appknox", "-y"]


def test_install_claude_plugin_raises_on_marketplace_add_failure(monkeypatch):
    _calls, fake_run = _record_run(
        results=[subprocess.CompletedProcess([], 1, "", "not found")]
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="marketplace add failed"):
        server._install_claude_plugin()


def test_install_claude_plugin_raises_on_install_failure(monkeypatch):
    _calls, fake_run = _record_run(
        results=[
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 1, "", "plugin not found"),
        ]
    )
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="plugin install failed"):
        server._install_claude_plugin()


def test_main_install_claude_plugin_flag_exits_without_starting_server(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["appknox-mcp", "--install-claude-plugin"])
    _no_server_start(monkeypatch)
    _calls, fake_run = _record_run()
    monkeypatch.setattr(subprocess, "run", fake_run)

    server.main()  # must not raise / must not start the server


def test_main_remove_client_flag_removes_entry(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = tmp_path / ".cursor" / "mcp.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"mcpServers": {"appknox": {"command": "appknox-mcp"}}}))
    monkeypatch.setattr(sys, "argv", ["appknox-mcp", "--remove-client", "cursor"])
    _no_server_start(monkeypatch)

    server.main()

    assert "appknox" not in json.loads(path.read_text())["mcpServers"]
