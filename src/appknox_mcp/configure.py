"""Write (or merge) the Appknox MCP server config for a given MCP client.

Kept dependency-free (stdlib only) so it also runs standalone via
``scripts/configure_mcp.py`` under any Python 3.11+ without a virtualenv or
project sync — see that file. Living inside the installed package additionally
lets ``appknox-mcp --configure``/``--remove-client`` call straight into this
module with no repo checkout at all, for anyone who installed from PyPI.

Existing config files are merged, never clobbered — only the ``appknox``
server entry is added or replaced.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SERVER_KEY = "appknox"
TOKEN_ENV = "APPKNOX_ACCESS_TOKEN"
# Matches both [mcp_servers.appknox] and [mcp_servers.appknox.env] — the single
# definition both _write_codex_toml and _remove_codex_toml key off of, so they
# can't drift apart on what counts as "the block".
_CODEX_BLOCK_PREFIX = f"[mcp_servers.{SERVER_KEY}"


def _claude_desktop_path(home: Path) -> Path:
    """Return Claude Desktop's config path for the current OS."""
    if sys.platform == "darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    if sys.platform.startswith("win"):
        return (
            Path(os.environ.get("APPDATA", home))
            / "Claude"
            / "claude_desktop_config.json"
        )
    return home / ".config" / "Claude" / "claude_desktop_config.json"


def _json_entry(repo_dir: str, token: str, base_url: str) -> dict:
    """Run-from-source entry: launches the server via ``uv run --directory <repo>``."""
    return {
        "command": "uv",
        "args": ["run", "--directory", repo_dir, "appknox-mcp"],
        "env": {"APPKNOX_ACCESS_TOKEN": token, "APPKNOX_BASE_URL": base_url},
    }


def _copilot_home(home: Path) -> Path:
    """Return the GitHub Copilot CLI config dir, honoring $COPILOT_HOME."""
    override = os.environ.get("COPILOT_HOME")
    return Path(override) if override else home / ".copilot"


def _tool_entry(token: str, base_url: str) -> dict:
    """Installed-tool entry: launches the bare ``appknox-mcp`` command on PATH.

    Used after ``uv tool install`` so the config has no dependency on the repo's
    location (nothing to break if the checkout moves).
    """
    return {
        "command": "appknox-mcp",
        "args": [],
        "env": {"APPKNOX_ACCESS_TOKEN": token, "APPKNOX_BASE_URL": base_url},
    }


def _write_json(
    path: Path, top_key: str, entry: dict, extra: dict | None = None
) -> None:
    """Merge ``entry`` under ``top_key`` into the JSON file at ``path``.

    ``extra`` holds keys merged into the entry itself (e.g. VS Code's ``type``).
    Preserves any other servers already configured in the file.
    """
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text() or "{}")
        except json.JSONDecodeError as exc:
            raise SystemExit(
                f"✗ {path} is not valid JSON ({exc}); fix or remove it first."
            )
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
        f"{_CODEX_BLOCK_PREFIX}]\n"
        f'command = "{entry["command"]}"\n'
        f"args = [{args}]\n\n"
        f"{_CODEX_BLOCK_PREFIX}.env]\n"
        f'APPKNOX_ACCESS_TOKEN = "{entry["env"]["APPKNOX_ACCESS_TOKEN"]}"\n'
        f'APPKNOX_BASE_URL = "{entry["env"]["APPKNOX_BASE_URL"]}"\n'
    )
    existing = path.read_text() if path.exists() else ""
    if _CODEX_BLOCK_PREFIX in existing:
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
        raise SystemExit(
            f"✗ {path} is not valid JSON ({exc}); fix or remove it manually."
        )
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
            skipping = stripped.startswith(_CODEX_BLOCK_PREFIX)
            removed = removed or skipping
        if not skipping:
            kept.append(line)
    if not removed:
        print(f"• No '{SERVER_KEY}' block in {path} — nothing to remove.")
        return
    text = "\n".join(kept).rstrip("\n")
    path.write_text(text + "\n" if text else "")
    print(f"✓ Removed {SERVER_KEY} server from {path}")


def _claude_mcp_remove() -> None:
    """Best-effort remove — a no-op (ignored) if the entry doesn't exist."""
    subprocess.run(
        ["claude", "mcp", "remove", SERVER_KEY, "--scope", "user"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _claude_mcp_add(entry: dict) -> None:
    """Register with Claude Code's OWN user-scope config (``~/.claude.json``),
    via the ``claude`` CLI — not a file this script writes itself.

    User scope means this works from any project on the device, not just the
    one it was run in. Unlike Claude Code's *plugin* .mcp.json (shared,
    versioned code — can't safely hold a personal secret) or the global `env`
    key in `settings.json` (broad, process-wide — Claude Code's own auto-mode
    classifier blocks writing a raw secret there), a literal value scoped to
    just this one server's own subprocess env is exactly what `claude mcp add`
    is for, and isn't blocked.

    Tries ``add`` directly first — the common case (first-time configure)
    needs only that one subprocess call. ``add`` errors instead of updating
    when the entry already exists, so only THEN do we pay for a remove +
    retry, rather than always removing pre-emptively.
    """
    args = ["claude", "mcp", "add", "--scope", "user"]
    for key, value in entry["env"].items():
        args += ["-e", f"{key}={value}"]
    # `--` stops `-e`'s variadic parsing from swallowing the positional args.
    args += ["--", SERVER_KEY, entry["command"], *entry["args"]]

    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0 and "already exists" in result.stderr + result.stdout:
        _claude_mcp_remove()
        result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(
            f"✗ claude mcp add failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    print(f"✓ Registered {SERVER_KEY} with Claude Code (user scope, all your projects)")


_CLIENTS = (
    "claude",
    "claude-desktop",
    "codex",
    "copilot",
    "cursor",
    "vscode",
    "windsurf",
)


def _target(client: str, home: Path, cwd: Path) -> tuple[str, Path]:
    """Map a FILE-based client name to (kind, config path). kind is 'json'|'vscode'|'codex'|'copilot'.

    Claude Code isn't here on purpose: it's configured via the ``claude`` CLI
    (see ``configure_client``/``remove_client``), not a file this script reads
    or writes — a different enough shape of side effect that folding it into
    this path-based table would leave ``path`` meaningless for that one case.
    """
    table = {
        # home-scoped
        "cursor": ("json", home / ".cursor" / "mcp.json"),
        "windsurf": ("json", home / ".codeium" / "windsurf" / "mcp_config.json"),
        "claude-desktop": ("json", _claude_desktop_path(home)),
        "copilot": ("copilot", _copilot_home(home) / "mcp-config.json"),
        # project-scoped
        "vscode": ("vscode", cwd / ".vscode" / "mcp.json"),
        "codex": ("codex", home / ".codex" / "config.toml"),
    }
    if client not in table:
        raise SystemExit(f"✗ Unknown client '{client}'. Choose: {', '.join(_CLIENTS)}")
    return table[client]


def _remove(kind: str, path: Path) -> None:
    """Remove the appknox server entry for a file-based config of the given kind."""
    if kind in ("json", "vscode", "copilot"):
        _remove_json(path, "servers" if kind == "vscode" else "mcpServers")
    elif kind == "codex":
        _remove_codex_toml(path)
    else:  # pragma: no cover - guarded by _target
        raise SystemExit(f"✗ Unhandled config kind '{kind}'")


def _write(kind: str, path: Path, entry: dict) -> None:
    """Write/merge the appknox server ``entry`` for a file-based config of the given kind."""
    if kind == "json":
        _write_json(path, "mcpServers", entry)
    elif kind == "vscode":
        _write_json(path, "servers", entry, extra={"type": "stdio"})
    elif kind == "codex":
        _write_codex_toml(path, entry)
    elif kind == "copilot":
        # Copilot CLI requires an explicit "type" (stdio == "local") and a
        # "tools" allowlist — without "tools": ["*"] it exposes none of the
        # server's tools even though the server itself starts fine.
        _write_json(path, "mcpServers", entry, extra={"type": "local", "tools": ["*"]})
    else:  # pragma: no cover - guarded by _target
        raise SystemExit(f"✗ Unhandled config kind '{kind}'")


def _build_entry(tool: bool, repo: str | None, token: str, base_url: str) -> dict:
    """Pick the run-from-source or installed-tool entry based on ``--tool``."""
    if tool:
        return _tool_entry(token, base_url)
    if not repo:
        raise SystemExit("✗ --repo is required unless --tool is given.")
    return _json_entry(repo, token, base_url)


def require_token() -> str:
    """Read the access token from the environment, or exit with a clear error.

    Never accept it as a CLI arg — argv is visible in `ps` and shell history.
    Shared by ``main()`` here and ``appknox-mcp --configure`` in server.py, so
    the env-var name and error message can't drift between the two.
    """
    token = os.environ.get(TOKEN_ENV, "")
    if not token:
        raise SystemExit(
            f"✗ {TOKEN_ENV} env var is required (format: <AccessKeyID>:<Secret>)."
        )
    return token


def configure_client(
    client: str,
    token: str,
    base_url: str,
    *,
    tool: bool = True,
    repo: str | None = None,
    cwd: Path | None = None,
) -> Path:
    """Write/merge the appknox entry for ``client``. Returns the config path written.

    ``tool=True`` (the default) is the right mode for anyone who installed via
    ``uv tool install``/``pip install`` — the config has no dependency on any
    repo location. Pass ``tool=False`` with ``repo`` for the run-from-source
    entry used by a cloned checkout.
    """
    entry = _build_entry(tool, repo, token, base_url)
    if client == "claude":
        _claude_mcp_add(entry)
        return Path.home() / ".claude.json"
    kind, path = _target(client, Path.home(), cwd or Path.cwd())
    _write(kind, path, entry)
    return path


def remove_client(client: str, *, cwd: Path | None = None) -> Path:
    """Remove the appknox entry for ``client``. Returns the config path touched."""
    if client == "claude":
        _claude_mcp_remove()
        return Path.home() / ".claude.json"
    kind, path = _target(client, Path.home(), cwd or Path.cwd())
    _remove(kind, path)
    return path


def main() -> None:
    """Parse args and write (or, with --remove, delete) the config for a client."""
    parser = argparse.ArgumentParser(
        description="Configure the Appknox MCP server for a client."
    )
    parser.add_argument("--client", required=True)
    parser.add_argument(
        "--repo", help="Absolute path to the MCP repo (run-from-source mode)."
    )
    parser.add_argument(
        "--base-url", help="Appknox Public API base URL (required unless --remove)."
    )
    parser.add_argument("--cwd", default=".", help="Dir for project-scoped configs.")
    parser.add_argument(
        "--tool",
        action="store_true",
        help="Config for a `uv tool install`ed server (bare `appknox-mcp` command, no repo path).",
    )
    parser.add_argument(
        "--remove", action="store_true", help="Remove the appknox server entry."
    )
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()

    if args.remove:
        remove_client(args.client, cwd=cwd)
        return

    if not args.base_url:
        raise SystemExit("✗ --base-url is required when writing config.")
    configure_client(
        args.client,
        require_token(),
        args.base_url,
        tool=args.tool,
        repo=args.repo,
        cwd=cwd,
    )


if __name__ == "__main__":
    main()
