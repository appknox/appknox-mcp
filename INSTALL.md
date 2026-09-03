# Installing the Appknox MCP server

This document is written so an **AI coding agent** (Claude Code, Cursor, Codex, …)
can install and wire up the Appknox MCP server end-to-end. A human can follow it
too. It needs no clone of this repo — the server installs as a global command.

> **Agent:** if a user handed you this repo's URL (or this file) and said "install
> it," you're in the right place — do the steps below in order. The only things to
> ask the user for are their **Access Key ID + Secret Access Key** (step 2) and,
> if it's unclear, **which client** to configure. Never print the secret back.

## 0. Prerequisite: `uv`

If `uv` is not on PATH, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh      # macOS/Linux
# Windows PowerShell: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then ensure `~/.local/bin` is on PATH (the installer usually handles this).

## 1. Install the server as a global tool

**You (the agent) run these commands** — the user doesn't. Try them **in order,
stopping at the first that works**; all produce a location-independent
`appknox-mcp` command on PATH (usually `~/.local/bin/appknox-mcp`).

**a) From PyPI (preferred — try this first).**
```bash
uv tool install appknox-mcp
```
This fails with a "not found" style error until the package is actually
published (tracked by `.github/workflows/publish.yml` in this repo) — that's
expected for now, just fall through to (b). Once it's live, this is the only
step that ever runs.

**b) From a released wheel.**
The repo is **private for now**, so download the wheel with the GitHub CLI (it
uses the user's existing `gh`/GitHub auth), then install the local file:

```bash
gh release download --repo appknox/appknox-mcp --pattern '*.whl' --dir /tmp/appknox-mcp
uv tool install /tmp/appknox-mcp/*.whl
```
Add `<tag>` (e.g. `v0.1.0`) as the first arg to `gh release download` to pin a
version; omit it for the latest. **When the repo is public**, skip `gh` entirely
and install straight from the asset URL:
`uv tool install "https://github.com/appknox/appknox-mcp/releases/latest/download/appknox_mcp-<version>-py3-none-any.whl"`.

**c) From git (no release needed).**
```bash
uv tool install "git+ssh://git@github.com/appknox/appknox-mcp@develop"   # private: uses the user's SSH key
# public: uv tool install "git+https://github.com/appknox/appknox-mcp@develop"
```

**d) From a local checkout** (if the user already cloned it):
`uv tool install /path/to/appknox-mcp`.

Then verify — if this prints a path, the server is installed and no repo folder is
needed afterward (nothing to keep or that can move):

```bash
command -v appknox-mcp
```

To update later: `uv tool upgrade appknox-mcp` (works regardless of which
source it was originally installed from) or re-run the `gh release download` +
`uv tool install --reinstall` step for a newer wheel.

## 2. Ask the user for credentials

Prompt the user for three things (from Appknox dashboard → **Service Accounts**):

1. **Access Key ID**
2. **Secret Access Key**
3. **Base URL** — the API host for their Appknox instance. Don't assume a
   default: white-labeled deployments use a different host, so ask rather than
   guess (their dashboard has it if they're unsure; Appknox's own KnoxIQ beta
   host is `https://sherlock-mcp.staging.appknox.io`, for reference only).

Combine the first two into the token the server expects:
`APPKNOX_ACCESS_TOKEN = "<Access Key ID>:<Secret Access Key>"` (a single colon
between them). Hold these in memory for step 3 — never echo the secret back to
the user or write it anywhere except the client config's `env`.

## 3. Write the MCP config for the client

Figure out which client you're configuring (if you're an agent, that's usually
the client you're running in; otherwise ask). **Merge** the `appknox` entry into
the existing config — never overwrite other servers. Use `command: "appknox-mcp"`
with **no args** (the tool install put it on PATH).

### JSON clients — Cursor, Claude Desktop, Windsurf, Claude Code

Key is `mcpServers`. Files:

| Client | Config file |
|---|---|
| Cursor | `~/.cursor/mcp.json` |
| Claude Desktop (macOS) | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Claude Desktop (Linux) | `~/.config/Claude/claude_desktop_config.json` |
| Claude Desktop (Windows) | `%APPDATA%\Claude\claude_desktop_config.json` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| Claude Code (this project) | `.mcp.json` in the repo |

```json
{
  "mcpServers": {
    "appknox": {
      "command": "appknox-mcp",
      "env": {
        "APPKNOX_ACCESS_TOKEN": "<Access Key ID>:<Secret Access Key>",
        "APPKNOX_BASE_URL": "<your Appknox base URL>"
      }
    }
  }
}
```

### GitHub Copilot CLI — `~/.copilot/mcp-config.json`

Key is `mcpServers` too, but each entry additionally needs `"type": "local"`
(Copilot CLI's name for a stdio server) and a `"tools"` allowlist — omit
`"tools"` and the server starts but exposes none of its tools:

```json
{
  "mcpServers": {
    "appknox": {
      "type": "local",
      "command": "appknox-mcp",
      "args": [],
      "env": {
        "APPKNOX_ACCESS_TOKEN": "<Access Key ID>:<Secret Access Key>",
        "APPKNOX_BASE_URL": "<your Appknox base URL>"
      },
      "tools": ["*"]
    }
  }
}
```

The path honors `$COPILOT_HOME` if set (defaults to `~/.copilot`). Verify with
`/mcp` inside a `copilot` session.

> **Note:** this is the standalone **GitHub Copilot CLI**, not Copilot Chat
> inside VS Code — that one is configured via the **VS Code** section below
> (VS Code's `.vscode/mcp.json` is shared by both plain VS Code MCP support and
> Copilot Chat).

### VS Code — `.vscode/mcp.json`

Key is `servers` and the entry needs `"type": "stdio"`:

```json
{
  "servers": {
    "appknox": {
      "type": "stdio",
      "command": "appknox-mcp",
      "env": { "APPKNOX_ACCESS_TOKEN": "…", "APPKNOX_BASE_URL": "…" }
    }
  }
}
```

### Codex — `~/.codex/config.toml`

The env vars **must** go under a nested `[mcp_servers.appknox.env]` table, or
Codex silently ignores them:

```toml
[mcp_servers.appknox]
command = "appknox-mcp"
args = []

[mcp_servers.appknox.env]
APPKNOX_ACCESS_TOKEN = "<Access Key ID>:<Secret Access Key>"
APPKNOX_BASE_URL = "<your Appknox base URL>"
```

> If the user cloned this repo, you can instead let the bundled writer do the
> merge (handles the Codex nesting for you):
> `python scripts/configure_mcp.py --client <name> --tool --base-url <url>`
> with `APPKNOX_ACCESS_TOKEN` set in the environment.

### Keep project-scoped tokens out of git

For `claude` (`.mcp.json`) and `vscode` (`.vscode/mcp.json`), which live in the
app repo and now contain the token, add the file to that repo's `.gitignore`.

### Claude Code only: the plugin (slash commands + fixer agent)

The MCP config above gets Claude Code the **tools**, but not `/appknox:triage`,
`/appknox:fix`, `/appknox:upload`, `/appknox:verify`, or the `appknox-fixer`
sub-agent — those only load if this repo is installed as a Claude Code
**plugin**, which is a separate registration:

```bash
claude plugin marketplace add appknox/appknox-mcp   # or a local clone's path
claude plugin install appknox@appknox -y
```

This installs at **user scope** (the default), so the commands/agent are
available from any repo afterward, not just the one you ran this in. Commands
are namespaced `/appknox:<name>` (Claude Code's plugin system always prefixes
`<plugin>:<command>` — there's no way to opt out of that and still use the
formal plugin mechanism). Its bundled MCP entry reads `APPKNOX_ACCESS_TOKEN`/
`APPKNOX_BASE_URL` from the environment at launch — export them in the user's
shell profile, or rely on the project-scoped `.mcp.json` above (token baked in,
works without exporting anything, but only in that one repo).
`scripts/install.sh`/`install.ps1` do this step automatically when Claude Code
is selected.

## 4. Restart and verify

MCP servers are spawned when the client starts, so **restart the client** (fully
quit Claude Desktop with Cmd+Q; restart the Codex or Copilot CLI session; reopen
Cursor). Then:

- Claude Code / Codex / Copilot CLI: run `/mcp` — you should see `appknox` with
  ~9 tools.
- Claude Code only: run `claude plugin list` — you should see `appknox@appknox`
  enabled; try `/appknox:triage` to confirm the slash commands loaded.
- Ask: *"list the Appknox tools"* — the agent should see `resolve_latest_file`,
  `list_analyses`, `knoxiq_get_fix_plan`, `knoxiq_prepare_fix`,
  `knoxiq_verify_fixes`, etc.

## 5. Update / uninstall

```bash
uv tool upgrade appknox-mcp          # pull the latest server
uv tool uninstall appknox-mcp        # remove the server
```

After uninstalling, also delete the `appknox` entry from the client config(s)
(or run `scripts/uninstall.sh <client>` from a clone — `scripts/uninstall.ps1
<client>` on Windows; for `claude` this also removes the plugin). To remove just
the plugin by hand: `claude plugin uninstall appknox@appknox` then
`claude plugin marketplace remove appknox`.
