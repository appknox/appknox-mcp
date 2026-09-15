#!/usr/bin/env bash
#
# Remove the Appknox KnoxIQ MCP server from an MCP client.
#
#   ./scripts/uninstall.sh [client]
#
# client ∈ cursor | claude-desktop | codex | copilot | windsurf | vscode | claude
#          (prompted if omitted)
#
# Only the `appknox` server entry is deleted; any other servers in the config are
# left untouched. No credentials are read or needed. This does not uninstall uv
# or the repo — just the client's pointer to this server.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALID_CLIENTS="cursor claude-desktop codex copilot windsurf vscode claude"

info()  { printf '  %s\n' "$1"; }
step()  { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }
die()   { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

CLIENT="${1:-}"
if [ -z "$CLIENT" ]; then
  step "Which client?"
  info "Options: $VALID_CLIENTS"
  printf '  client> '
  read -r CLIENT
fi
case " $VALID_CLIENTS " in *" $CLIENT "*) ;; *) die "Unknown client '$CLIENT'. Choose one of: $VALID_CLIENTS";; esac

step "Removing appknox from $CLIENT config"
# Prefer uv (matches install), but fall back to a bare python3 so uninstall works
# even if the environment is half torn down.
if command -v uv >/dev/null 2>&1; then
  uv run --no-project --directory "$REPO_DIR" python "$REPO_DIR/scripts/configure_mcp.py" \
    --client "$CLIENT" --cwd "$PWD" --remove
else
  python3 "$REPO_DIR/scripts/configure_mcp.py" --client "$CLIENT" --cwd "$PWD" --remove
fi

if [ "$CLIENT" = "claude" ] && command -v claude >/dev/null 2>&1; then
  step "Removing the appknox plugin (slash commands + fixer agent)"
  claude plugin uninstall appknox@appknox -y >/dev/null 2>&1 || true
  claude plugin marketplace remove appknox >/dev/null 2>&1 || true
  info "✓ Plugin and marketplace entry removed (user scope)"
fi

step "Done"
info "Restart $CLIENT so it drops the server and its tools."
