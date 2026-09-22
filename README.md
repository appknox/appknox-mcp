# Appknox MCP Server

An [MCP](https://modelcontextprotocol.io) server that connects your AI coding
agent to [Appknox](https://www.appknox.com) KnoxIQ, so it can **fetch the
vulnerabilities Appknox found in your app, fix them in your repo, and verify each
fix with the finding's own proof-of-concept** — without leaving your editor.

Works with any MCP-capable agent. Verified with **Claude**, **Codex**,
**Copilot**, **Cursor**, and **Windsurf** — anything else that speaks MCP
should work too.

---

## Install

Two ways: **ask your agent** (no clone, recommended) or **run the guided script**.

<details>
<summary><strong>Option A — Ask your agent (no clone)</strong></summary>

If you already have an AI coding agent running (Claude Code, Cursor, Codex, …),
paste this — the install guide bundled in the package has every remaining step
(credentials, client config, the Claude Code plugin, restarting), so there's
nothing else to keep in sync here:

```
Install the appknox-mcp MCP server for me:
1. `uv tool install --reinstall appknox-mcp` —
   **always include `--reinstall`**: without it, `uv` silently does nothing if
   any version is already installed, even a stale one missing this exact flag.
2. Run `appknox-mcp --install-guide` and follow it exactly.
```

That's it — the agent installs it, reads the guide, asks you for credentials,
writes the config, and tells you to restart the client.

</details>

<details>
<summary><strong>Option B — Guided script (auto-detects your clients)</strong></summary>

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
manual steps). It prompts for your token (hidden input) and your base URL (no
default offered — always ask, since white-labeled deployments use a different
host), merges the server into each selected client's config without touching
anything else, and git-ignores any token-bearing config. **If Claude Code is
selected**, it also installs the plugin (`claude plugin marketplace add` +
`claude plugin install`, user scope) so the `/appknox:*` slash commands and the
fixer agent are available from any repo, not just this one. Then **restart the
client(s)**.

> Name clients directly to skip detection: `./scripts/install.sh cursor codex`
> (or `.\scripts\install.ps1 cursor codex` on Windows).
> Set `APPKNOX_ACCESS_TOKEN` / `APPKNOX_BASE_URL` beforehand to skip the prompts.

Full step-by-step, per-client config paths, and by-hand setup: [INSTALL.md](INSTALL.md).

</details>

---

## Verify it's connected

MCP servers only load at startup, so **restart the client first**, then check
it picked up `appknox`:

<details>
<summary><strong>Claude Code</strong></summary>

Run `/mcp` in any session — it's registered at user scope, so this works in
any project, not just one repo — you should see `appknox` listed with ~9
tools. If you also installed the plugin, try `/appknox:triage` to confirm the
slash commands loaded (this needs the plugin's own credentials — see
[INSTALL.md](INSTALL.md) for the env-var export it relies on).
</details>

<details>
<summary><strong>Claude Desktop</strong></summary>

Fully quit (Cmd+Q) and reopen — it only reads config at launch. Then either:
- click the hammer/tools icon in the chat input and look for `resolve_latest_file`,
  `list_analyses`, etc., or
- click **+** below the chat box → **Connectors**, or
- go to **Settings → Developer** to see the server's status and logs.
</details>

<details>
<summary><strong>Codex CLI</strong></summary>

Restart the Codex session, then run `/mcp` — `appknox` should appear in the
server list.
</details>

<details>
<summary><strong>GitHub Copilot CLI</strong></summary>

Restart your `copilot` session, then run `/mcp` inside it — or run
`copilot mcp list` directly from your shell. Either should show `appknox`.

**Also run with `--allow-all-mcp-server-instructions`** (v1.0.66+) if you want
the guided workflow (resolve → triage → fix → verify, exploitability shown by
default, etc.) — Copilot CLI doesn't feed any MCP server's instructions to the
model without it, so without this flag it'll still call the tools correctly
but skip the intended flow unless you spell each step out yourself.
</details>

<details>
<summary><strong>Cursor</strong></summary>

Restart Cursor, then open **Settings → MCP**. `appknox` should show a green
dot with a tool count next to it. (Green dot but 0 tools? Cursor caps tools at
40 across *all* enabled servers combined — check what else you have enabled.)
</details>

<details>
<summary><strong>Windsurf</strong></summary>

Restart Windsurf, then click the **MCPs** icon in the top-right of the Cascade
panel — `appknox` should show a green status indicator with its tools listed
underneath.
</details>

<details>
<summary><strong>VS Code (incl. Copilot Chat)</strong></summary>

Reload the window (Command Palette → **Developer: Reload Window**), then
Command Palette → **MCP: List Servers** — `appknox` should appear with
start/stop/restart options. Once started, open Copilot Chat and check the
tools icon next to the model picker — `appknox`'s tools should be listed and
toggled on there.
</details>

---

## Usage

Inside your app's repository, once the server is connected:

### First run — resolving which build to check

The tools work against a specific Appknox **file_id** (a scanned build). You
don't need to look one up:

- **Don't mention one** and the agent detects your app's `package_name` (and
  Android/iOS platform) from the repo, resolves it to the latest scanned build
  on Appknox, and tells you which build it found before doing anything else —
  confirm it or point it at a different one.
- **Already have a file_id** (e.g. checking an older build on purpose)? Just
  say so — it's used directly, after a quick check that it's still current.

```
You:   Find and fix the Appknox vulnerabilities in this repo.
Agent: No file_id given — I'll detect this app from the repo and use its
       latest scanned build. Found com.appknox.demo (Android), latest is
       file_id 48213 (v3.2.1, scanned 2 days ago). Use this one?
You:   Yes.
Agent: [checks scan readiness, then lists vulnerabilities by exploitability…]
```

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

### Getting your Access Key ID and Secret Access Key

These credentials come from a Service Account in Appknox, which must be
created by a user with **Owner** privileges in your organization.

To create one:

1. Log in to Appknox and go to **Organization Settings**.
2. Open the **Service Accounts** tab.
3. Create a new service account and set its scope to at least:
   - **Projects**: Read
   - **Scan Results (VA)**: Read
   - **Upload App**: Write
4. Under **Project Access**, select **All Projects** (or the specific projects
   you want the MCP to access).
5. Generate the service account — Appknox will provide an **Access Key ID**
   and **Secret Access Key**. Copy both and use them when installing the
   Appknox MCP.

> **Note:** If you don't have Owner privileges, ask an Owner in your
> organization to create the service account for you.

| Environment Variable | Required | Default | Description |
|---|---|---|---|
| `APPKNOX_ACCESS_TOKEN` | Yes | — | `<Access Key ID>:<Secret Access Key>` |
| `APPKNOX_BASE_URL` | No | `https://publicapi.appknox.com` | Appknox Public API host |

Per-client config file paths and shapes: [INSTALL.md](INSTALL.md#3-write-the-mcp-config-for-the-client).

---

## Uninstall

**Installed via Option A (no clone)?** Use the bundled command — it needs
nothing but the package you already have:
```bash
appknox-mcp --remove-client cursor        # same client names as install
```
Then, to remove the package itself: `uv tool uninstall appknox-mcp`.

**Installed via Option B (cloned the repo)?** Use the installer scripts —
functionally identical, just also cleans up the Claude Code plugin registration:
```bash
./scripts/uninstall.sh cursor        # same client names as install
```
```powershell
.\scripts\uninstall.ps1 cursor       # Windows
```

Either way, only the `appknox` entry is removed from that client's config;
nothing else is touched. Restart the client afterwards.
