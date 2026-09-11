# Installing the Appknox MCP server

This document is written so an **AI coding agent** (Claude Code, Cursor, Codex, …)
can install and wire up the Appknox MCP server end-to-end. A human can follow it
too. It needs no clone of this repo — the server installs as a global command,
and this exact file ships inside the package: once step 1 below is done, run
`appknox-mcp --install-guide` any time to print it again.

> **Agent:** if a user handed you this repo's URL (or this file) and said "install
> it," you're in the right place — do the steps below in order. **First identify
> which client you are actually running as** (Claude Code, Cursor, Codex, GitHub
> Copilot CLI, VS Code, Windsurf, Claude Desktop, or something else) — you need
> this for step 3 regardless, and it matters more once you reach the section
> titled "Claude Code only": if you are not Claude Code, skip that entire
> section (do not run its commands "just in case" or because it looked like the
> next step in order) and go straight to the step after it. The only things to
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

> **Always include `--reinstall`** on every `uv tool install` below, even the
> very first attempt. Without it, `uv` silently does **nothing** if any
> version of `appknox-mcp` is already installed — including a stale one that
> predates a flag like `--install-guide` — so re-running "install" can look
> like it worked while actually leaving old, broken code in place. This is a
> real failure mode that has happened, not a hypothetical edge case.

**a) From PyPI (preferred — try this first).**
```bash
uv tool install --reinstall appknox-mcp
```
Not live yet — while `appknox-mcp` is only on TestPyPI, install from there
instead (needs `--extra-index-url` since deps like `fastmcp` aren't on
TestPyPI, and `--index-strategy unsafe-best-match` to let `uv` resolve across
both indexes):
```bash
uv tool install --reinstall --index https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ --index-strategy unsafe-best-match appknox-mcp
```
Once it's on real PyPI, switch to the plain command above and skip straight to
verifying — only fall through to (b) if both of these fail.

**b) From a released wheel.**
The repo is **private for now**, so download the wheel with the GitHub CLI (it
uses the user's existing `gh`/GitHub auth), then install the local file:

```bash
gh release download --repo appknox/appknox-mcp --pattern '*.whl' --dir /tmp/appknox-mcp
uv tool install --reinstall /tmp/appknox-mcp/*.whl
```
Add `<tag>` (e.g. `v0.1.0`) as the first arg to `gh release download` to pin a
version; omit it for the latest. **When the repo is public**, skip `gh` entirely
and install straight from the asset URL:
`uv tool install --reinstall "https://github.com/appknox/appknox-mcp/releases/latest/download/appknox_mcp-<version>-py3-none-any.whl"`.

**c) From git (no release needed).**
```bash
uv tool install --reinstall "git+ssh://git@github.com/appknox/appknox-mcp@develop"   # private: uses the user's SSH key
# public: uv tool install --reinstall "git+https://github.com/appknox/appknox-mcp@develop"
```

**d) From a local checkout** (if the user already cloned it):
`uv tool install --reinstall /path/to/appknox-mcp`.

Then verify — `command -v appknox-mcp` only proves *a* binary is on PATH, not
that it's actually the one you just installed (a stale prior install would
also pass that check silently, as `--reinstall` above exists specifically to
prevent). Confirm the real thing instead:

```bash
appknox-mcp --install-guide | head -1
```

If that doesn't print `# Installing the Appknox MCP server`, the install
didn't actually take — re-run step 1's command with `--reinstall` (if you
skipped it) rather than assuming this step is broken.

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

> **Important — Copilot CLI ignores this server's workflow guidance by
> default.** Every MCP server can send high-level instructions alongside its
> tools (ours describes the resolve → triage → fix → verify flow, how to
> select findings, etc.) — Copilot CLI deliberately does **not** feed these
> into the model unless you start it with `copilot --allow-all-mcp-server-instructions`
> (v1.0.66+). Without that flag, Copilot only sees each tool's own
> name/parameters/docstring, not the overall workflow — it can still call the
> tools correctly, but won't follow the intended multi-step flow or
> presentation guidance (e.g. showing exploitability) unless asked explicitly
> each time. Recommend this flag to anyone using Copilot CLI who wants the
> guided experience the other clients get by default.

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

This is project-scoped (only active in this one repo), unlike every other
client here — `appknox-mcp --configure vscode` writes the same project-scoped
file, we don't automate the alternative below. VS Code does have a genuine
**user-scope** option (works in every workspace): Command Palette → **MCP:
Open User Configuration**, or `code --add-mcp '{"name":"appknox",...}'` and
choose **Global** over **Workspace**. VS Code's own docs recommend *against* a
literal secret even there — use an `${input:...}` variable (`password: true`)
instead, which prompts once and caches the value in VS Code's own secret
storage from then on. Set that up by hand if you want VS Code to behave like
the other clients here; see [VS Code's MCP docs](https://code.visualstudio.com/docs/copilot/customization/mcp-servers)
for the exact `inputs` array syntax.

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

> You can skip writing any of the JSON/TOML above by hand and instead let the
> already-installed `appknox-mcp` command do the merge for you (handles the
> Codex nesting, Copilot's `type`/`tools` fields, etc. correctly) — works with
> **no repo clone needed**, since the writer ships inside the package itself:
> `APPKNOX_ACCESS_TOKEN=<id>:<secret> appknox-mcp --configure <name> --base-url <url>`.
> To remove an entry later: `appknox-mcp --remove-client <name>`.

### Keep project-scoped tokens out of git

`vscode` (`.vscode/mcp.json`) lives in the app repo and now contains the
token — add it to that repo's `.gitignore`. `claude` no longer needs this: it
registers at user scope (`~/.claude.json`, outside any repo), not a
project-scoped file.

### Claude Code only: the plugin (slash commands + fixer agent)

> **STOP — agent, check this first:** this section applies ONLY if you are
> Claude Code. If you are Copilot CLI, Cursor, Codex, VS Code, Windsurf, Claude
> Desktop, or anything else, **skip this entire section** — do not run
> `claude plugin ...` commands (the `claude` CLI likely isn't even installed in
> your environment, and this step is not part of your setup at all) — and
> continue at "4. Restart and verify" below.

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

Before (or instead of) removing the server itself, remove its entry from each
client's config: `appknox-mcp --remove-client <client>` — this needs no repo
clone, since it ships inside the package (see the note in step 3). If the repo
happens to be cloned, `scripts/uninstall.sh <client>`/`scripts/uninstall.ps1
<client>` do the same thing and additionally remove the Claude Code plugin
registration for `claude`. To remove just the plugin by hand:
`claude plugin uninstall appknox@appknox` then
`claude plugin marketplace remove appknox`.
