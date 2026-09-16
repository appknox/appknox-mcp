#!/usr/bin/env bash
#
# Install the Appknox KnoxIQ MCP server into your MCP-capable IDE(s)/CLI(s).
#
#   ./scripts/install.sh                 # auto-detect clients, then multi-select
#   ./scripts/install.sh cursor codex    # install into the named clients directly
#
# Supported: cursor | claude-desktop | codex | copilot | windsurf | vscode | claude
#
# The access token is read from $APPKNOX_ACCESS_TOKEN, or prompted (never echoed,
# never placed on the command line). Existing client configs are merged, not
# overwritten. Clients we can't configure automatically get printed generic steps.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_BASE_URL="https://sherlock-mcp.staging.appknox.io"
# Detection order = display order.
ALL_CLIENTS=(cursor claude-desktop codex copilot windsurf vscode claude)

info()  { printf '  %s\n' "$1"; }
step()  { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }
warn()  { printf '\033[33m  %s\033[0m\n' "$1"; }
die()   { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

client_label() {
  case "$1" in
    cursor)         echo "Cursor" ;;
    claude-desktop) echo "Claude Desktop" ;;
    codex)          echo "Codex CLI" ;;
    copilot)        echo "GitHub Copilot CLI" ;;
    windsurf)       echo "Windsurf" ;;
    vscode)         echo "VS Code (project: this repo)" ;;
    claude)         echo "Claude Code (project: this repo)" ;;
    *)              echo "$1" ;;
  esac
}

client_hint() {
  case "$1" in
    cursor)         echo "Restart Cursor; enable 'appknox' under Settings → MCP if it's off." ;;
    claude-desktop) echo "Fully quit and reopen Claude Desktop (Cmd+Q) so it respawns MCP servers." ;;
    codex)          echo "Restart the Codex session; run /mcp to confirm 'appknox'." ;;
    copilot)        echo "Restart the Copilot CLI session; run /mcp to confirm 'appknox'." ;;
    windsurf)       echo "Restart Windsurf; enable the server in the MCP panel if needed." ;;
    vscode)         echo "Reload VS Code; start the server from .vscode/mcp.json." ;;
    claude)         echo "Restart Claude Code in this repo; run /appknox:triage or /appknox:fix." ;;
  esac
}

# Presence heuristics: an app bundle, a CLI on PATH, or the client's config dir.
is_present() {
  case "$1" in
    cursor)         [ -d "$HOME/.cursor" ] || [ -d "/Applications/Cursor.app" ] || command -v cursor >/dev/null 2>&1 ;;
    claude-desktop) [ -d "$HOME/Library/Application Support/Claude" ] || [ -d "/Applications/Claude.app" ] ;;
    codex)          command -v codex >/dev/null 2>&1 || [ -d "$HOME/.codex" ] ;;
    copilot)        command -v copilot >/dev/null 2>&1 || [ -d "$HOME/.copilot" ] ;;
    windsurf)       [ -d "$HOME/.codeium/windsurf" ] || [ -d "/Applications/Windsurf.app" ] || command -v windsurf >/dev/null 2>&1 ;;
    vscode)         command -v code >/dev/null 2>&1 || [ -d "/Applications/Visual Studio Code.app" ] || [ -d "$HOME/.vscode" ] ;;
    claude)         command -v claude >/dev/null 2>&1 || [ -d "$HOME/.claude" ] ;;
    *)              return 1 ;;
  esac
}

is_valid_client() {
  local c
  for c in "${ALL_CLIENTS[@]}"; do [ "$c" = "$1" ] && return 0; done
  return 1
}

# ---- 1. prerequisites -------------------------------------------------------
step "Checking prerequisites"
if ! command -v uv >/dev/null 2>&1; then
  info "uv (the Python package manager) is not installed."
  printf '  Install it now from https://astral.sh/uv? [Y/n] '
  read -r reply
  case "${reply:-Y}" in
    [Nn]*) die "uv is required. Install it (https://docs.astral.sh/uv/) and re-run." ;;
  esac
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # uv installs to ~/.local/bin (or ~/.cargo/bin on older installers); make sure it's on PATH now.
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv install finished but 'uv' isn't on PATH. Open a new shell and re-run."
fi
info "✓ uv found: $(command -v uv)"

# ---- 2. choose clients ------------------------------------------------------
SELECTED=()       # clients we will auto-configure
SHOW_GENERIC=0    # also print manual/generic steps

if [ "$#" -gt 0 ]; then
  # Explicit clients on the command line — skip detection.
  for c in "$@"; do
    is_valid_client "$c" || die "Unknown client '$c'. Choose from: ${ALL_CLIENTS[*]}"
    SELECTED+=("$c")
  done
else
  step "Detecting MCP-capable clients on your system"
  DETECTED=()
  for c in "${ALL_CLIENTS[@]}"; do
    if is_present "$c"; then DETECTED+=("$c"); fi
  done

  if [ "${#DETECTED[@]}" -eq 0 ]; then
    warn "None detected automatically."
    SHOW_GENERIC=1
  else
    info "Appknox detected these on your system:"
    i=1
    for c in "${DETECTED[@]}"; do
      printf '    %d) %s\n' "$i" "$(client_label "$c")"
      i=$((i + 1))
    done
    info "Select which to install the MCP into — space-separated numbers,"
    info "'a' for all detected, or 'm' for manual/generic steps (any other client)."
    printf '  select> '
    read -r answer
    for tok in $answer; do
      case "$tok" in
        a|A|all)      SELECTED=("${DETECTED[@]}") ;;
        m|M|manual)   SHOW_GENERIC=1 ;;
        ''|*[!0-9]*)  warn "Ignoring '$tok' (not a number/a/m)." ;;
        *)
          if [ "$tok" -ge 1 ] && [ "$tok" -le "${#DETECTED[@]}" ]; then
            SELECTED+=("${DETECTED[$((tok - 1))]}")
          else
            warn "Ignoring out-of-range choice '$tok'."
          fi
          ;;
      esac
    done
  fi
fi

# De-duplicate SELECTED (e.g. user typed "a" plus a number).
if [ "${#SELECTED[@]}" -gt 0 ]; then
  SELECTED=($(printf '%s\n' "${SELECTED[@]}" | awk '!seen[$0]++'))
fi

if [ "${#SELECTED[@]}" -eq 0 ] && [ "$SHOW_GENERIC" -eq 0 ]; then
  die "Nothing selected. Re-run and pick at least one client (or 'm' for manual steps)."
fi

# ---- 3. credentials (only if we're writing at least one config) -------------
# No default base URL: white-labeled Appknox deployments use a different host
# than the standard one, so guessing wrong here would silently point a
# customer's agent at the wrong instance. Always ask.
BASE_URL="${APPKNOX_BASE_URL:-}"
if [ "${#SELECTED[@]}" -gt 0 ]; then
  step "Credentials"
  if [ -z "${APPKNOX_ACCESS_TOKEN:-}" ]; then
    info "Format: <Access Key ID>:<Secret Access Key>  (input hidden)"
    printf '  token> '
    read -rs APPKNOX_ACCESS_TOKEN
    printf '\n'
  fi
  [ -n "${APPKNOX_ACCESS_TOKEN:-}" ] || die "No access token provided."
  export APPKNOX_ACCESS_TOKEN

  if [ -z "${BASE_URL:-}" ]; then
    info "The Appknox Public API host for your instance — check your dashboard if unsure."
    info "(e.g. $DEFAULT_BASE_URL for Appknox's own KnoxIQ beta — white-labeled"
    info "deployments use a different host, so don't assume this one.)"
    printf '  base URL> '
    read -r BASE_URL
  fi
  [ -n "${BASE_URL:-}" ] || die "No base URL provided."
  info "✓ Using base URL: $BASE_URL"
fi

# ---- 4. write each selected client's config ---------------------------------
# Project-scoped configs (claude/.mcp.json, vscode/.vscode/mcp.json) hold the
# token in the CURRENT repo — keep them out of git.
ensure_gitignored() {
  local entry="$1"
  [ -d "$PWD/.git" ] || return 0
  local gi="$PWD/.gitignore"
  if [ ! -f "$gi" ] || ! grep -qxF "$entry" "$gi" 2>/dev/null; then
    printf '%s\n' "$entry" >> "$gi"
    info "✓ Added '$entry' to .gitignore (holds your token)"
  fi
}

# Claude Code also gets this as a plugin (marketplace-installed at user scope):
# the plugin adds the /appknox:<name> slash commands + fixer agent — it does
# NOT provide the working MCP connection with real credentials (its own
# bundled .mcp.json reads $APPKNOX_ACCESS_TOKEN/$APPKNOX_BASE_URL from the
# environment, since that file is shared plugin code, not a personal config).
# The actual credentialed connection is the `claude mcp add --scope user` call
# above (configure_mcp.py's "claude" client) — this just adds the commands on
# top of it. Commands are namespaced /appknox:<name> — the plugin system
# always prefixes <plugin>:<command>, no opt-out.
install_claude_plugin() {
  if ! command -v claude >/dev/null 2>&1; then
    warn "claude CLI not found — skipping plugin install (commands/agent won't be available)."
    return
  fi
  claude plugin marketplace add "$REPO_DIR" --scope user >/dev/null
  claude plugin install appknox@appknox -y >/dev/null
  info "✓ Installed the appknox plugin (slash commands + fixer agent, user scope)"
  warn "The plugin's OWN MCP entry (separate from the one just registered above)"
  warn "reads \$APPKNOX_ACCESS_TOKEN/\$APPKNOX_BASE_URL from your shell at launch —"
  warn "export them in your shell profile if /appknox:* commands need it too."
}

for CLIENT in "${SELECTED[@]}"; do
  step "Configuring $(client_label "$CLIENT")"
  # --no-project: configure_mcp.py is stdlib-only, so this needs a compatible
  # interpreter, not the server's runtime deps — skip syncing them.
  uv run --no-project --directory "$REPO_DIR" python "$REPO_DIR/scripts/configure_mcp.py" \
    --client "$CLIENT" --repo "$REPO_DIR" --base-url "$BASE_URL" --cwd "$PWD"
  case "$CLIENT" in
    claude) install_claude_plugin ;;
    vscode) ensure_gitignored ".vscode/mcp.json" ;;
  esac
  info "→ $(client_hint "$CLIENT")"
done

# ---- 5. generic / manual steps for unknown clients --------------------------
if [ "$SHOW_GENERIC" -eq 1 ]; then
  step "Manual setup (any other MCP client)"
  cat <<EOF
  Add this server to the client's MCP config. JSON clients use the key
  "mcpServers"; put your real token in place of the placeholder:

    "appknox": {
      "command": "uv",
      "args": ["run", "--directory", "$REPO_DIR", "appknox-mcp"],
      "env": {
        "APPKNOX_ACCESS_TOKEN": "<Access Key ID>:<Secret Access Key>",
        "APPKNOX_BASE_URL": "https://publicapi.appknox.com"
      }
    }

  • VS Code:  key is "servers" and the entry needs  "type": "stdio"
  • Codex:    ~/.codex/config.toml — env vars go under a NESTED
              [mcp_servers.appknox.env] table (see README → Manual configuration)
  • Copilot CLI: ~/.copilot/mcp-config.json — entry needs "type": "local" and
              "tools": ["*"] (see README → Manual configuration)
EOF
fi

# ---- 6. done ----------------------------------------------------------------
step "Done"
if [ "${#SELECTED[@]}" -gt 0 ]; then
  info "Configured: ${SELECTED[*]}"
  info "From inside an app repo, ask the agent to find & fix vulnerabilities."
  info "Claude Code: /appknox:triage (browse+fix all) or /appknox:fix <analysis_id> (one vuln)."
  info "Other clients: just ask, e.g. \"fix Appknox analysis 405 in this repo\"."
  info "To remove later: ./scripts/uninstall.sh"
fi
