"""Tests for appknox_mcp.configure (writes/merges MCP client configs).

scripts/configure_mcp.py is a thin shim over this module for the repo-clone
path — not tested separately here since it has no logic of its own to test.
"""

import json
import subprocess
from pathlib import Path

import pytest

from appknox_mcp import configure as configure_mcp

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
    entry = configure_mcp._build_entry(
        tool=True, repo=None, token=TOKEN, base_url=BASE_URL
    )
    assert entry["command"] == "appknox-mcp"


def test_build_entry_source_mode_requires_repo() -> None:
    with pytest.raises(SystemExit, match="--repo is required"):
        configure_mcp._build_entry(
            tool=False, repo=None, token=TOKEN, base_url=BASE_URL
        )


def test_configure_client_writes_tool_entry_with_no_repo_needed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The no-clone path: appknox-mcp --configure calls this directly."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = configure_mcp.configure_client("cursor", TOKEN, BASE_URL)
    assert path == tmp_path / ".cursor" / "mcp.json"
    entry = json.loads(path.read_text())["mcpServers"]["appknox"]
    assert entry["command"] == "appknox-mcp"  # tool mode by default, no repo path
    assert entry["env"]["APPKNOX_ACCESS_TOKEN"] == TOKEN


def test_remove_client_deletes_the_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    configure_mcp.configure_client("cursor", TOKEN, BASE_URL)
    path = configure_mcp.remove_client("cursor")
    data = json.loads(path.read_text())
    assert "appknox" not in data["mcpServers"]


def test_write_json_preserves_existing_servers(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}}))
    configure_mcp._write_json(
        path, "mcpServers", configure_mcp._json_entry(REPO, TOKEN, BASE_URL)
    )
    data = json.loads(path.read_text())
    assert "other" in data["mcpServers"]  # untouched
    assert data["mcpServers"]["appknox"]["command"] == "uv"


def test_write_json_creates_missing_file(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "mcp.json"
    configure_mcp._write_json(
        path, "mcpServers", configure_mcp._json_entry(REPO, TOKEN, BASE_URL)
    )
    assert path.exists()
    assert (
        json.loads(path.read_text())["mcpServers"]["appknox"]["env"][
            "APPKNOX_ACCESS_TOKEN"
        ]
        == TOKEN
    )


def test_write_json_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text("{not json")
    with pytest.raises(SystemExit, match="not valid JSON"):
        configure_mcp._write_json(path, "mcpServers", {"command": "uv"})


def test_vscode_entry_gets_type_stdio(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    configure_mcp._write_json(
        path,
        "servers",
        configure_mcp._json_entry(REPO, TOKEN, BASE_URL),
        extra={"type": "stdio"},
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


def test_copilot_entry_gets_type_local_and_tools(tmp_path: Path) -> None:
    path = tmp_path / "mcp-config.json"
    configure_mcp._write_json(
        path,
        "mcpServers",
        configure_mcp._json_entry(REPO, TOKEN, BASE_URL),
        extra={"type": "local", "tools": ["*"]},
    )
    entry = json.loads(path.read_text())["mcpServers"]["appknox"]
    assert entry["type"] == "local"
    assert entry["tools"] == ["*"]


def test_target_copilot_path_defaults_to_home(monkeypatch) -> None:
    monkeypatch.delenv("COPILOT_HOME", raising=False)
    home, cwd = Path("/home/x"), Path("/repo")
    assert configure_mcp._target("copilot", home, cwd) == (
        "copilot",
        home / ".copilot" / "mcp-config.json",
    )


def test_target_copilot_path_honors_copilot_home(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_HOME", "/custom/copilot")
    home, cwd = Path("/home/x"), Path("/repo")
    assert configure_mcp._target("copilot", home, cwd) == (
        "copilot",
        Path("/custom/copilot") / "mcp-config.json",
    )


def test_target_unknown_client_raises() -> None:
    with pytest.raises(SystemExit, match="Unknown client"):
        configure_mcp._target("emacs", Path("/home/x"), Path("/repo"))


def test_target_paths(tmp_path: Path) -> None:
    home, cwd = Path("/home/x"), Path("/repo")
    assert configure_mcp._target("cursor", home, cwd) == (
        "json",
        home / ".cursor" / "mcp.json",
    )
    assert configure_mcp._target("codex", home, cwd) == (
        "codex",
        home / ".codex" / "config.toml",
    )
    assert configure_mcp._target("vscode", home, cwd) == (
        "vscode",
        cwd / ".vscode" / "mcp.json",
    )


def test_target_does_not_handle_claude() -> None:
    """Claude Code is routed to the `claude` CLI by configure_client/remove_client
    directly, never through the file-based _target table — see the
    test_configure_client_claude_* tests below for that path."""
    with pytest.raises(SystemExit, match="Unknown client"):
        configure_mcp._target("claude", Path("/home/x"), Path("/repo"))


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


def test_claude_mcp_add_succeeds_on_first_try_without_remove(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The common case: fresh configure needs only one subprocess call."""
    calls, fake_run = _record_run()
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    configure_mcp._claude_mcp_add(configure_mcp._tool_entry(TOKEN, BASE_URL))

    assert calls == [
        [
            "claude",
            "mcp",
            "add",
            "--scope",
            "user",
            "-e",
            f"APPKNOX_ACCESS_TOKEN={TOKEN}",
            "-e",
            f"APPKNOX_BASE_URL={BASE_URL}",
            "--",
            "appknox",
            "appknox-mcp",
        ]
    ]


def test_claude_mcp_add_includes_source_mode_args(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, fake_run = _record_run()
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    configure_mcp._claude_mcp_add(configure_mcp._json_entry(REPO, TOKEN, BASE_URL))

    assert calls[0][-7:] == [
        "--",
        "appknox",
        "uv",
        "run",
        "--directory",
        REPO,
        "appknox-mcp",
    ]


def test_claude_mcp_add_retries_via_remove_when_already_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the update case pays for remove + retry, not the common fresh case."""
    add_args = [
        "claude",
        "mcp",
        "add",
        "--scope",
        "user",
        "-e",
        f"APPKNOX_ACCESS_TOKEN={TOKEN}",
        "-e",
        f"APPKNOX_BASE_URL={BASE_URL}",
        "--",
        "appknox",
        "appknox-mcp",
    ]
    calls, fake_run = _record_run(
        results=[
            subprocess.CompletedProcess(
                add_args, 1, "", "MCP server appknox already exists"
            ),
            subprocess.CompletedProcess([], 0, "", ""),  # the remove
            subprocess.CompletedProcess(add_args, 0, "", ""),  # the retried add
        ]
    )
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    configure_mcp._claude_mcp_add(configure_mcp._tool_entry(TOKEN, BASE_URL))

    assert [c[:3] for c in calls] == [
        ["claude", "mcp", "add"],
        ["claude", "mcp", "remove"],
        ["claude", "mcp", "add"],
    ]


def test_claude_mcp_add_raises_immediately_on_non_conflict_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure unrelated to 'already exists' must not trigger a wasted
    remove+retry — it should raise straight away."""
    calls, fake_run = _record_run(
        results=[subprocess.CompletedProcess([], 1, "", "some other error")]
    )
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="some other error"):
        configure_mcp._claude_mcp_add(configure_mcp._tool_entry(TOKEN, BASE_URL))

    assert len(calls) == 1


def test_claude_mcp_add_raises_final_error_if_retry_also_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _calls, fake_run = _record_run(
        results=[
            subprocess.CompletedProcess([], 1, "", "MCP server appknox already exists"),
            subprocess.CompletedProcess([], 0, "", ""),  # the remove
            subprocess.CompletedProcess(
                [], 1, "", "still broken"
            ),  # retried add fails too
        ]
    )
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    with pytest.raises(SystemExit, match="still broken"):
        configure_mcp._claude_mcp_add(configure_mcp._tool_entry(TOKEN, BASE_URL))


def test_claude_mcp_remove_is_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """Must not raise even when the server doesn't exist (nothing to remove)."""
    monkeypatch.setattr(
        configure_mcp.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess([], 1, "", "no such server"),
    )
    configure_mcp._claude_mcp_remove()  # should not raise


def test_claude_mcp_remove_uses_scope_flag_consistent_with_add(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression check for the `-s` vs `--scope` inconsistency."""
    calls, fake_run = _record_run()
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)
    configure_mcp._claude_mcp_remove()
    assert calls == [["claude", "mcp", "remove", "appknox", "--scope", "user"]]


def test_configure_client_claude_routes_to_claude_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, fake_run = _record_run()
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    path = configure_mcp.configure_client("claude", TOKEN, BASE_URL)

    assert path == tmp_path / ".claude.json"
    assert calls[0][:3] == ["claude", "mcp", "add"]


def test_remove_client_claude_routes_to_claude_cli(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    calls, fake_run = _record_run()
    monkeypatch.setattr(configure_mcp.subprocess, "run", fake_run)

    path = configure_mcp.remove_client("claude")

    assert path == tmp_path / ".claude.json"
    assert calls[0][:3] == ["claude", "mcp", "remove"]


def test_require_token_returns_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPKNOX_ACCESS_TOKEN", TOKEN)
    assert configure_mcp.require_token() == TOKEN


def test_require_token_raises_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APPKNOX_ACCESS_TOKEN", raising=False)
    with pytest.raises(SystemExit, match="APPKNOX_ACCESS_TOKEN"):
        configure_mcp.require_token()


def test_target_claude_desktop_is_json_and_named_correctly() -> None:
    home, cwd = Path("/home/x"), Path("/repo")
    kind, path = configure_mcp._target("claude-desktop", home, cwd)
    assert kind == "json"
    assert path.name == "claude_desktop_config.json"
    assert "Claude" in path.parts


def test_remove_json_deletes_only_appknox(tmp_path: Path) -> None:
    path = tmp_path / "mcp.json"
    path.write_text(
        json.dumps(
            {"mcpServers": {"appknox": {"command": "uv"}, "other": {"command": "x"}}}
        )
    )
    configure_mcp._remove_json(path, "mcpServers")
    data = json.loads(path.read_text())
    assert "appknox" not in data["mcpServers"]
    assert "other" in data["mcpServers"]  # untouched


def test_remove_json_missing_file_is_noop(tmp_path: Path) -> None:
    # Should not raise when there's nothing to remove.
    configure_mcp._remove_json(tmp_path / "absent.json", "mcpServers")


def test_remove_codex_toml_strips_block_keeps_rest(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    configure_mcp._write_codex_toml(
        path, configure_mcp._json_entry(REPO, TOKEN, BASE_URL)
    )
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
