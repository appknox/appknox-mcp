"""Entry point for the Appknox KnoxIQ stdio MCP server."""

import argparse
import importlib.resources
import sys
from pathlib import Path

# Tool modules register their @mcp.tool tools on import.
from appknox_mcp import (  # noqa: F401
    findings,
    resolve,
    status,
    upload,
    verify,
)
from appknox_mcp.app import access_token, mcp


def _print_install_guide() -> None:
    """Print the setup guide — works from any install method (uv tool, pipx,
    pip), with no repo clone or network fetch needed.

    INSTALL.md is only copied next to the package at build time (see
    pyproject.toml's force-include), so an editable/source checkout won't have
    it there — fall back to the repo's actual top-level copy in that case.
    """
    try:
        text = (
            importlib.resources.files("appknox_mcp").joinpath("INSTALL.md").read_text()
        )
    except FileNotFoundError:
        repo_root = Path(__file__).resolve().parent.parent.parent
        text = (repo_root / "INSTALL.md").read_text()
    print(text)


def _install_claude_plugin() -> None:
    """Register the Claude Code plugin (slash commands + fixer agent) with no
    repo clone and no GitHub access at all.

    ``claude plugin marketplace add owner/repo`` has Claude Code itself clone
    the repo — that doesn't reliably work against a private repo (no
    gh/keychain credential passthrough; a known Claude Code limitation) and
    only ever looks at the repo's default branch. Sidestep both problems by
    extracting the plugin files this wheel already bundles (see
    pyproject.toml's force-include) to a stable local directory and pointing
    ``claude plugin marketplace add`` at *that* — the local-path form, which
    needs no cloning of anything.

    The target directory is wiped and re-extracted every run, so re-running
    this after ``uv tool upgrade`` picks up a newer bundled plugin.
    """
    import shutil
    import subprocess

    target = Path.home() / ".appknox-mcp" / "claude-plugin"
    try:
        bundled = importlib.resources.files("appknox_mcp").joinpath("claude_plugin")
        with importlib.resources.as_file(bundled) as src:
            if not src.is_dir():
                raise FileNotFoundError
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
    except FileNotFoundError:
        # Editable/source checkout: the force-include copy only exists in a
        # built wheel (see _print_install_guide's identical fallback) — use
        # the repo's actual top-level files directly instead of extracting.
        repo_root = Path(__file__).resolve().parent.parent.parent
        target = repo_root

    result = subprocess.run(
        ["claude", "plugin", "marketplace", "add", str(target), "--scope", "user"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"✗ claude plugin marketplace add failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    result = subprocess.run(
        ["claude", "plugin", "install", "appknox@appknox", "-y"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"✗ claude plugin install failed: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    print(f"✓ Registered the Claude Code plugin from {target}")


def _configure_client(client: str, base_url: str) -> None:
    """Write/merge this server into ``client``'s MCP config — the no-clone path.

    Always ``tool`` mode (bare ``appknox-mcp`` command): anyone reaching this
    CLI flag already has the package installed, so there's no repo path to
    reference and no ``--repo``/``--tool`` distinction to expose here.

    Imports ``configure`` locally: that module (and its ``subprocess``/``json``
    imports) is only needed for this rare path, not the server's normal
    startup — every other launch of ``appknox-mcp`` shouldn't pay for it.
    """
    from appknox_mcp import configure

    configure.configure_client(client, configure.require_token(), base_url)


def main() -> None:
    """Run the stdio MCP server.

    A missing token warns rather than exits: exiting mid-handshake surfaces to
    clients as an opaque connection error, so instead the tools appear and each
    call fails with a clear auth error until the token is set.
    """
    parser = argparse.ArgumentParser(prog="appknox-mcp")
    parser.add_argument(
        "--install-guide",
        action="store_true",
        help="Print the setup guide (credentials, client config) and exit.",
    )
    parser.add_argument(
        "--configure",
        metavar="CLIENT",
        help=(
            "Write/merge this server into CLIENT's MCP config (cursor, "
            "claude-desktop, windsurf, copilot, codex, claude, vscode). Reads "
            "the token from APPKNOX_ACCESS_TOKEN; needs --base-url."
        ),
    )
    parser.add_argument(
        "--remove-client",
        metavar="CLIENT",
        help="Remove this server's entry from CLIENT's MCP config.",
    )
    parser.add_argument(
        "--install-claude-plugin",
        action="store_true",
        help=(
            "Register the Claude Code plugin (slash commands + fixer agent) "
            "with no repo clone or GitHub access needed. Requires the `claude` "
            "CLI on PATH."
        ),
    )
    parser.add_argument("--base-url", help="API base URL — required with --configure.")
    args = parser.parse_args()

    if args.install_guide:
        _print_install_guide()
        return
    if args.install_claude_plugin:
        _install_claude_plugin()
        return
    if args.configure:
        if not args.base_url:
            raise SystemExit("✗ --base-url is required with --configure.")
        _configure_client(args.configure, args.base_url)
        return
    if args.remove_client:
        from appknox_mcp import configure

        configure.remove_client(args.remove_client)
        return

    if not access_token:
        print(
            "Warning: APPKNOX_ACCESS_TOKEN is not set — tool calls will fail with an "
            "auth error until it is configured (format <Access Key ID>:<Secret>).",
            file=sys.stderr,
        )
    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
