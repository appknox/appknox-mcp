# Appknox MCP Server

An [MCP](https://modelcontextprotocol.io) server that connects your AI coding
agent to [Appknox](https://www.appknox.com) KnoxIQ, so it can **fetch the
vulnerabilities Appknox found in your app, fix them in your repo, and verify each
fix with the finding's own proof-of-concept** — without leaving your editor.

Works with **Claude Code**, **Claude Desktop**, **Codex**, **Cursor**, Windsurf,
and VS Code.

---

## Install

Two ways: **ask your agent** (no clone, recommended) or **run the guided script**.

### Option A — Ask your agent (no clone)

If you already have an AI coding agent running (Claude Code, Cursor, Codex, …),
tell it to install this — it uses its own shell + file tools to install the server
and write your MCP config. **Paste this prompt:**

> Install the Appknox KnoxIQ MCP server for me:
> 1. If `uv` isn't installed, install it (https://astral.sh/uv).
> 2. Install the server as a global tool. Try, in order:
>    `gh release download --repo appknox/appknox-mcp --pattern '*.whl' --dir /tmp/appknox-mcp && uv tool install /tmp/appknox-mcp/*.whl`
>    — else `uv tool install "git+ssh://git@github.com/appknox/appknox-mcp@main"`. Verify with `command -v appknox-mcp`.
> 3. Ask me for my Appknox **Access Key ID**, **Secret Access Key**, and **base URL** (default `https://sherlock-mcp.staging.appknox.io`).
> 4. Add an `appknox` MCP server to this client's config: `command: "appknox-mcp"`, env `APPKNOX_ACCESS_TOKEN=<id>:<secret>` and `APPKNOX_BASE_URL=<url>`.
> 5. If this client is **Claude Code**, also install the plugin — it's the only
>    way to get the `/appknox:*` slash commands and the fixer agent (an MCP
>    entry alone does not add them): `claude plugin marketplace add
>    appknox/appknox-mcp` then `claude plugin install appknox@appknox -y`.
> 6. Tell me to restart the client.

The agent installs it, asks for your credentials, writes the config, and you
restart — done. Installed as a global tool, so the config has no dependency on any
folder; update later with `uv tool upgrade appknox-mcp`.

### Option B — Guided script (auto-detects your clients)

Prefer a deterministic install? Clone and run the installer — macOS, Linux, and
Windows all get the identical flow and write identical config, just via a
`.sh` or `.ps1` wrapper around the same Python backend:

**macOS / Linux / WSL / Git Bash:**
```bash
git clone git@github.com:appknox/appknox-mcp.git
cd appknox-mcp
./scripts/install.sh
```

**Windows (PowerShell):**
```powershell
git clone git@github.com:appknox/appknox-mcp.git
cd appknox-mcp
.\scripts\install.ps1
```

It installs `uv` if missing, **auto-detects the MCP clients on your machine**, and
lets you pick which to configure (space-separated numbers, `a` for all, or `m` for
manual steps). It prompts for your token (hidden input), merges the server into
each selected client's config without touching anything else, and git-ignores any
token-bearing config. **If Claude Code is selected**, it also installs the plugin
(`claude plugin marketplace add` + `claude plugin install`, user scope) so the
`/appknox:*` slash commands and the fixer agent are available from any repo, not
just this one. Then **restart the client(s)**.

> Name clients directly to skip detection: `./scripts/install.sh cursor codex`
> (or `.\scripts\install.ps1 cursor codex` on Windows).
> Set `APPKNOX_ACCESS_TOKEN` / `APPKNOX_BASE_URL` beforehand to skip the prompts.

Full step-by-step, per-client config paths, and by-hand setup: [INSTALL.md](INSTALL.md).

### Uninstall

```bash
./scripts/uninstall.sh cursor        # same client names as install
```
```powershell
.\scripts\uninstall.ps1 cursor       # Windows
```

Removes only the `appknox` entry from that client's config; nothing else is
touched. Restart the client afterwards.

---

## Usage

Inside your app's repository, once the server is connected:

### Claude Code

| Command | What it does |
|---|---|
| `/appknox:triage` | Lists KnoxIQ vulnerabilities for the latest scanned build and — on your selection — fixes them, verifying each with its PoC. |
| `/appknox:fix <selection>` | Fixes the finding(s) you name — a single **analysis_id**, `all`, a **severity**, or an **exploitability range** (`highly exploitable`) — and verifies each with its PoC. Optional `file_id` second arg. |
| `/appknox:upload <binary-path>` | Uploads a built binary (APK/IPA/…) to Appknox and starts a fresh scan; returns the new `file_id`. |
| `/appknox:verify <new_file_id> [old_file_id]` | Compares the re-scanned build to report which vulnerabilities are **resolved** vs **still open**. |

No `file_id` needed for triage/fix — the app is resolved from the repo's
`package_name`. If KnoxIQ isn't enabled or the scan isn't ready, the command says
so instead of showing an empty list.

Full loop: `/appknox:triage` → fix → build → `/appknox:upload` → `/appknox:verify`.

### Any other client (Codex, Cursor, Claude Desktop, …)

No slash commands, but the same workflow is built into the server, so just ask:

- *"Find and fix the Appknox vulnerabilities in this repo."*
- *"Fix Appknox analysis 405."* / *"Fix all highly exploitable findings."*
- *"Upload build/app-release.apk to Appknox."*
- *"Did my fixes work? Compare build 987 against 950."*

The fixes are left **staged** for you to review — the commands never commit. A
local PoC check is confidence, not proof; the Appknox re-scan is the ground truth.

---

## Credentials

Create a service account in the Appknox dashboard under **Service Accounts** and
copy the **Access Key ID** and **Secret Access Token**. The token format is
`<Access Key ID>:<Secret Access Key>`.

| Environment Variable | Required | Default | Description |
|---|---|---|---|
| `APPKNOX_ACCESS_TOKEN` | Yes | — | `<Access Key ID>:<Secret Access Key>` |
| `APPKNOX_BASE_URL` | No | `https://publicapi.appknox.com` | API host (use staging while KnoxIQ is in beta) |

Per-client config file paths and shapes: [INSTALL.md](INSTALL.md#3-write-the-mcp-config-for-the-client).

---

## Tools

Generic Appknox platform tools:

| Tool | Purpose |
|---|---|
| `resolve_latest_file(package_name, platform)` | Resolve an app identifier to its Appknox project and latest scanned `file_id`. |
| `get_file_info(file_id)` | App identity + scan summary (package, version, platform, per-severity counts). |
| `list_analyses(file_id, …)` | One row per analysis (vulnerability) for the file, filtered by risk; optionally enriched with KnoxIQ exploitability. |
| `upload_binary(file_path, …)` | Upload a built binary to the Appknox VAPT platform and start a scan; returns the new `file_id`. |

KnoxIQ tools (prefixed `knoxiq_`; require KnoxIQ to be enabled):

| Tool | Purpose |
|---|---|
| `knoxiq_get_scan_status(file_id)` | Whether the scan + KnoxIQ analysis are ready, with an actionable message when they're not. |
| `knoxiq_get_fix_plan(file_id, analysis_ids)` | Full fix payload (`developer_prompt`, `remediation`, `poc`) for chosen findings. |
| `knoxiq_prepare_fix(file_id, analysis_id)` | The full fix payload for **one** vulnerability in a single call. |
| `knoxiq_verify_fixes(new_file_id, …)` | Compare a re-scanned build: which fixed vulnerabilities are resolved vs still open. |

---

## Development

```bash
uv sync
uv run pytest
```

- Entry point: `src/appknox_mcp/server.py` (`appknox-mcp` console script).
- Core: `app.py` (shared mcp + client instance), `client.py` (the Appknox API SDK —
  every endpoint call lives here), `instructions.py` (the workflow).
- Tools: `resolve.py`, `findings.py`, `status.py`, `upload.py`, `verify.py` — each
  calls `client`'s named methods, never raw URLs.
- Installer: `scripts/` — `install.sh`/`uninstall.sh` (macOS/Linux/WSL) and
  `install.ps1`/`uninstall.ps1` (Windows) are thin wrappers around the same
  `configure_mcp.py`, which does the actual (cross-platform, stdlib-only)
  config read/write.
- Claude Code plugin: `commands/`, `agents/`, `.claude-plugin/` (`plugin.json`
  manifest + `marketplace.json` for self-hosting). Commands are namespaced
  `/appknox:<name>` — `install.sh`/`install.ps1` install it via `claude plugin
  marketplace add` + `claude plugin install`, at user scope.
