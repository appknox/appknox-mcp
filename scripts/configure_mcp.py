"""Write (or merge) the Appknox MCP server config for a given MCP client.

Called by ``install.sh``. Kept dependency-free (stdlib only) so it runs under any
Python 3.11+ without a virtualenv. Existing config files are merged, never
clobbered — only the ``appknox`` server entry is added or replaced.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SERVER_KEY = "appknox"
TOKEN_ENV = "APPKNOX_ACCESS_TOKEN"


def _claude_desktop_path(home: Path) -> Path:
    """Return Claude Desktop's config path for the current OS."""
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", home)) / "Claude" / "claude_desktop_config.json"
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def _launch_args(repo_dir: str) -> list[str]:
    """Return the argv that starts the stdio server via uv."""
    return ["run", "--directory", repo_dir, "appknox-mcp"]


def _entry(command: str, args: list[str], token: str, base_url: str) -> dict:
    """Build a server entry dict for the given launch command/args."""
    return {
        "command": command,
        "args": args,
        "env": {
            "APPKNOX_ACCESS_TOKEN": token,
            "APPKNOX_BASE_URL": base_url,
        },
    }


def _json_entry(repo_dir: str, token: str, base_url: str) -> dict:
    """Run-from-source entry: launches the server via ``uv run --directory <repo>``."""
    return _entry("uv", _launch_args(repo_dir), token, base_url)


def _tool_entry(token: str, base_url: str) -> dict:
    """Installed-tool entry: launches the bare ``appknox-mcp`` command on PATH.

    Used after ``uv tool install`` so the config has no dependency on the repo's
    location (nothing to break if the checkout moves).
    """
    return _entry("appknox-mcp", [], token, base_url)


def _write_json(path: Path, top_key: str, entry: dict, extra: dict | None = None) -> None:
    """Merge ``entry`` under ``top_key`` into the JSON file at ``path``.

    ``extra`` holds keys merged into the entry itself (e.g. VS Code's ``type``).
    Preserves any other servers already configured in the file.
    """
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text() or "{}")
        except json.JSONDecodeError as exc:
            raise SystemExit(f"✗ {path} is not valid JSON ({exc}); fix or remove it first.")
    servers = data.setdefault(top_key, {})
    servers[SERVER_KEY] = {**entry, **(extra or {})}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"✓ Wrote {SERVER_KEY} server to {path}")


def _write_codex_toml(path: Path, entry: dict) -> None:
    """Append (or replace) the ``[mcp_servers.appknox]`` block in Codex's TOML.

    No TOML writer is in the stdlib, so we regenerate the block as text from the
    server ``entry`` (command/args/env) and leave the rest of the file intact.
    The env vars go under a NESTED ``[mcp_servers.appknox.env]`` table — Codex
    silently ignores them if they sit directly under the server table.
    """
    args = ", ".join(f'"{a}"' for a in entry["args"])
    block = (
        f"[mcp_servers.{SERVER_KEY}]\n"
        f'command = "{entry["command"]}"\n'
        f"args = [{args}]\n\n"
        f"[mcp_servers.{SERVER_KEY}.env]\n"
        f'APPKNOX_ACCESS_TOKEN = "{entry["env"]["APPKNOX_ACCESS_TOKEN"]}"\n'
        f'APPKNOX_BASE_URL = "{entry["env"]["APPKNOX_BASE_URL"]}"\n'
    )
    existing = path.read_text() if path.exists() else ""
    if f"[mcp_servers.{SERVER_KEY}" in existing:
        print(
            f"⚠ {path} already has an '{SERVER_KEY}' block — leaving it untouched.\n"
            f"  To update, delete the [mcp_servers.{SERVER_KEY}] and "
            f"[mcp_servers.{SERVER_KEY}.env] tables and re-run."
        )
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    sep = "" if existing.endswith("\n") or not existing else "\n"
    path.write_text(existing + sep + ("\n" if existing else "") + block)
    print(f"✓ Appended {SERVER_KEY} server to {path}")


def _remove_json(path: Path, top_key: str) -> None:
    """Remove the ``appknox`` server entry from a JSON config, leaving others intact."""
    if not path.exists():
        print(f"• {path} does not exist — nothing to remove.")
        return
    try:
        data = json.loads(path.read_text() or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"✗ {path} is not valid JSON ({exc}); fix or remove it manually.")
    servers = data.get(top_key, {})
    if SERVER_KEY not in servers:
        print(f"• No '{SERVER_KEY}' server in {path} — nothing to remove.")
        return
    del servers[SERVER_KEY]
    path.write_text(json.dumps(data, indent=2) + "\n")
    print(f"✓ Removed {SERVER_KEY} server from {path}")


def _remove_codex_toml(path: Path) -> None:
    """Strip the ``[mcp_servers.appknox]`` and ``.env`` tables from Codex's TOML."""
    if not path.exists():
        print(f"• {path} does not exist — nothing to remove.")
        return
    kept, removed, skipping = [], False, False
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            # A new table header ends any block we were skipping.
            skipping = stripped.startswith(f"[mcp_servers.{SERVER_KEY}")
            removed = removed or skipping
        if not skipping:
            kept.append(line)
    if not removed:
        print(f"• No '{SERVER_KEY}' block in {path} — nothing to remove.")
        return
    text = "\n".join(kept).rstrip("\n")
    path.write_text(text + "\n" if text else "")
    print(f"✓ Removed {SERVER_KEY} server from {path}")


def _target(client: str, home: Path, cwd: Path) -> tuple[str, Path]:
    """Map a client name to (kind, config path). kind is 'json'|'vscode'|'codex'."""
    home_json = {
        "cursor": ("json", home / ".cursor" / "mcp.json"),
        "windsurf": ("json", home / ".codeium" / "windsurf" / "mcp_config.json"),
        "claude-desktop": ("json", _claude_desktop_path(home)),
    }
    project = {
        "claude": ("json", cwd / ".mcp.json"),
        "vscode": ("vscode", cwd / ".vscode" / "mcp.json"),
        "codex": ("codex", home / ".codex" / "config.toml"),
    }
    table = {**home_json, **project}
    if client not in table:
        raise SystemExit(f"✗ Unknown client '{client}'. Choose: {', '.join(sorted(table))}")
    return table[client]


def _remove(kind: str, path: Path) -> None:
    """Remove the appknox server entry for a config of the given kind."""
    if kind in ("json", "vscode"):
        _remove_json(path, "servers" if kind == "vscode" else "mcpServers")
    elif kind == "codex":
        _remove_codex_toml(path)
    else:  # pragma: no cover - guarded by _target
        raise SystemExit(f"✗ Unhandled config kind '{kind}'")


def _write(kind: str, path: Path, entry: dict) -> None:
    """Write/merge the appknox server ``entry`` for a config of the given kind."""
    if kind == "json":
        _write_json(path, "mcpServers", entry)
    elif kind == "vscode":
        _write_json(path, "servers", entry, extra={"type": "stdio"})
    elif kind == "codex":
        _write_codex_toml(path, entry)
    else:  # pragma: no cover - guarded by _target
        raise SystemExit(f"✗ Unhandled config kind '{kind}'")


def _build_entry(tool: bool, repo: str | None, token: str, base_url: str) -> dict:
    """Pick the run-from-source or installed-tool entry based on ``--tool``."""
    if tool:
        return _tool_entry(token, base_url)
    if not repo:
        raise SystemExit("✗ --repo is required unless --tool is given.")
    return _json_entry(repo, token, base_url)


def main() -> None:
    """Parse args and write (or, with --remove, delete) the config for a client."""
    parser = argparse.ArgumentParser(description="Configure the Appknox MCP server for a client.")
    parser.add_argument("--client", required=True)
    parser.add_argument("--repo", help="Absolute path to the MCP repo (run-from-source mode).")
    parser.add_argument("--base-url", help="API base URL (required unless --remove).")
    parser.add_argument("--cwd", default=".", help="Dir for project-scoped configs.")
    parser.add_argument(
        "--tool",
        action="store_true",
        help="Config for a `uv tool install`ed server (bare `appknox-mcp` command, no repo path).",
    )
    parser.add_argument("--remove", action="store_true", help="Remove the appknox server entry.")
    args = parser.parse_args()

    kind, path = _target(args.client, Path.home(), Path(args.cwd).resolve())

    if args.remove:
        _remove(kind, path)
        return

    if not args.base_url:
        raise SystemExit("✗ --base-url is required when writing config.")
    # Read the secret from the environment, never argv — argv is visible in `ps`
    # and shell history.
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        raise SystemExit(f"✗ {TOKEN_ENV} env var is required (format: <AccessKeyID>:<Secret>).")
    _write(kind, path, _build_entry(args.tool, args.repo, token, args.base_url))


if __name__ == "__main__":
    sys.exit(main())
