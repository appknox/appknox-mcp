"""Entry point for the Appknox KnoxIQ stdio MCP server."""

import argparse
import importlib.resources
import sys
from pathlib import Path

from appknox_mcp.app import access_token, mcp

# Tool modules register their @mcp.tool tools on import.
from appknox_mcp import (  # noqa: E402, F401
    findings,
    resolve,
    status,
    upload,
    verify,
)


def _print_install_guide() -> None:
    """Print the setup guide — works from any install method (uv tool, pipx,
    pip), with no repo clone or network fetch needed.

    INSTALL.md is only copied next to the package at build time (see
    pyproject.toml's force-include), so an editable/source checkout won't have
    it there — fall back to the repo's actual top-level copy in that case.
    """
    try:
        text = importlib.resources.files("appknox_mcp").joinpath("INSTALL.md").read_text()
    except FileNotFoundError:
        repo_root = Path(__file__).resolve().parent.parent.parent
        text = (repo_root / "INSTALL.md").read_text()
    print(text)


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
    parser.add_argument("--base-url", help="API base URL — required with --configure.")
    args = parser.parse_args()

    if args.install_guide:
        _print_install_guide()
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
