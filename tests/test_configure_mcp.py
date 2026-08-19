"""Tests for scripts/configure_mcp.py (writes/merges MCP client configs)."""

import importlib.util
import json
from pathlib import Path

import pytest

# Load the script module by path (it lives in scripts/, not the package).
_SPEC = importlib.util.spec_from_file_location(
    "configure_mcp",
    Path(__file__).parent.parent / "scripts" / "configure_mcp.py",
)
configure_mcp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(configure_mcp)


REPO = "/opt/appknox-mcp"
TOKEN = "KEYID:secret"
BASE_URL = "https://sherlock-mcp.staging.appknox.io"


def test_json_entry_shape() -> None:
    entry = configure_mcp._json_entry(REPO, TOKEN, BASE_URL)
    assert entry["command"] == "uv"
    assert entry["args"] == ["run", "--directory", REPO, "appknox-mcp"]
    assert entry["env"]["APPKNOX_ACCESS_TOKEN"] == TOKEN
    assert entry["env"]["APPKNOX_BASE_URL"] == BASE_URL


def test_tool_entry_is_location_independent() -> None:
    entry = configure_mcp._tool_entry(TOKEN, BASE_URL)
    assert entry["command"] == "appknox-mcp"  # bare command on PATH
    assert entry["args"] == []  # no repo path baked in
    assert entry["env"]["APPKNOX_ACCESS_TOKEN"] == TOKEN


def test_build_entry_tool_mode_ignores_missing_repo() -> None:
    entry = configure_mcp._build_entry(tool=True, repo=None, token=TOKEN, base_url=BASE_URL)
    assert entry["command"] == "appknox-mcp"


def test_build_entry_source_mode_requires_repo() -> None:
    with pytest.raises(SystemExit, match="--repo is required"):
        configure_mcp._build_entry(tool=False, repo=None, token=TOKEN, base_url=BASE_URL)


def test_write_json_preserves_existing_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    configure_mcp._write_json(path, "mcpServers", configure_mcp._json_entry(REPO, TOKEN, BASE_URL))
    data = json.loads(path.read_text())
    assert "other" in data["mcpServers"]  # untouched
    assert data["mcpServers"]["appknox"]["command"] == "uv"


def test_write_json_creates_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "mcp.json"
    configure_mcp._write_json(path, "mcpServers", configure_mcp._json_entry(REPO, TOKEN, BASE_URL))
    assert path.exists()
    assert json.loads(path.read_text())["mcpServers"]["appknox"]["env"]["APPKNOX_ACCESS_TOKEN"] == TOKEN


def test_write_json_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text("{not json")
    with pytest.raises(SystemExit, match="not valid JSON"):
        configure_mcp._write_json(path, "mcpServers", {"command": "uv"})


def test_vscode_entry_gets_type_stdio(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    configure_mcp._write_json(
        path, "servers", configure_mcp._json_entry(REPO, TOKEN, BASE_URL), extra={"type": "stdio"}
    )
    assert json.loads(path.read_text())["servers"]["appknox"]["type"] == "stdio"


def test_codex_toml_append_and_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('model = "gpt-5"\n')
    entry = configure_mcp._json_entry(REPO, TOKEN, BASE_URL)
    configure_mcp._write_codex_toml(path, entry)
    text = path.read_text()
    assert 'model = "gpt-5"' in text  # existing config preserved
    assert "[mcp_servers.appknox]" in text
    assert "[mcp_servers.appknox.env]" in text  # env under the NESTED table
    assert f'APPKNOX_ACCESS_TOKEN = "{TOKEN}"' in text
    # Re-running must not duplicate the block.
    configure_mcp._write_codex_toml(path, entry)
    assert path.read_text().count("[mcp_servers.appknox]") == 1


def test_target_unknown_client_raises() -> None:
    with pytest.raises(SystemExit, match="Unknown client"):
        configure_mcp._target("emacs", Path("/home/x"), Path("/repo"))


def test_target_paths(tmp_path: Path) -> None:
    home, cwd = Path("/home/x"), Path("/repo")
    assert configure_mcp._target("cursor", home, cwd) == ("json", home / ".cursor" / "mcp.json")
    assert configure_mcp._target("codex", home, cwd) == ("codex", home / ".codex" / "config.toml")
    assert configure_mcp._target("claude", home, cwd) == ("json", cwd / ".mcp.json")
    assert configure_mcp._target("vscode", home, cwd) == ("vscode", cwd / ".vscode" / "mcp.json")


def test_target_claude_desktop_is_json_and_named_correctly() -> None:
    home, cwd = Path("/home/x"), Path("/repo")
    kind, path = configure_mcp._target("claude-desktop", home, cwd)
    assert kind == "json"
    assert path.name == "claude_desktop_config.json"
    assert "Claude" in path.parts


def test_remove_json_deletes_only_appknox(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"appknox": {"command": "uv"}, "other": {"command": "x"}}}))
    configure_mcp._remove_json(path, "mcpServers")
    data = json.loads(path.read_text())
    assert "appknox" not in data["mcpServers"]
    assert "other" in data["mcpServers"]  # untouched


def test_remove_json_missing_file_is_noop(tmp_path: Path) -> None:
    # Should not raise when there's nothing to remove.
    configure_mcp._remove_json(tmp_path / "absent.json", "mcpServers")


def test_remove_codex_toml_strips_block_keeps_rest(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    configure_mcp._write_codex_toml(path, configure_mcp._json_entry(REPO, TOKEN, BASE_URL))
    path.write_text('model = "gpt-5"\n\n' + path.read_text())
    configure_mcp._remove_codex_toml(path)
    text = path.read_text()
    assert 'model = "gpt-5"' in text  # unrelated config preserved
    assert "mcp_servers.appknox" not in text  # both the table and its .env table gone


def test_codex_toml_tool_mode_uses_bare_command(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    configure_mcp._write_codex_toml(path, configure_mcp._tool_entry(TOKEN, BASE_URL))
    text = path.read_text()
    assert 'command = "appknox-mcp"' in text  # bare command, not uv
    assert "args = []" in text  # no repo path baked in
    assert REPO not in text
