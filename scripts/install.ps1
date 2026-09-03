<#
.SYNOPSIS
    Install the Appknox KnoxIQ MCP server into your MCP-capable IDE(s)/CLI(s).

.DESCRIPTION
    Windows PowerShell counterpart to install.sh — same flow, same
    configure_mcp.py backend, so both scripts write identical config.

.EXAMPLE
    .\scripts\install.ps1                    # auto-detect clients, then multi-select
    .\scripts\install.ps1 cursor codex        # install into the named clients directly

.NOTES
    Supported: cursor | claude-desktop | codex | copilot | windsurf | vscode | claude

    The access token is read from $env:APPKNOX_ACCESS_TOKEN, or prompted (hidden
    input, never placed on the command line). Existing client configs are merged,
    not overwritten. Clients we can't configure automatically get printed generic
    steps.
#>

param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Clients = @()
)

$ErrorActionPreference = "Stop"

$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DefaultBaseUrl = "https://sherlock-mcp.staging.appknox.io"
# Detection order = display order.
$AllClients = @("cursor", "claude-desktop", "codex", "copilot", "windsurf", "vscode", "claude")

function Write-Info($msg) { Write-Host "  $msg" }
function Write-Step($msg) { Write-Host "`n▸ $msg" -ForegroundColor White }
function Write-Warn($msg) { Write-Host "  $msg" -ForegroundColor Yellow }
function Die($msg) { Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

function Get-ClientLabel($client) {
    switch ($client) {
        "cursor"         { "Cursor" }
        "claude-desktop" { "Claude Desktop" }
        "codex"          { "Codex CLI" }
        "copilot"        { "GitHub Copilot CLI" }
        "windsurf"       { "Windsurf" }
        "vscode"         { "VS Code (project: this repo)" }
        "claude"         { "Claude Code (project: this repo)" }
        default          { $client }
    }
}

function Get-ClientHint($client) {
    switch ($client) {
        "cursor"         { "Restart Cursor; enable 'appknox' under Settings -> MCP if it's off." }
        "claude-desktop" { "Fully quit and reopen Claude Desktop so it respawns MCP servers." }
        "codex"          { "Restart the Codex session; run /mcp to confirm 'appknox'." }
        "copilot"        { "Restart the Copilot CLI session; run /mcp to confirm 'appknox'." }
        "windsurf"       { "Restart Windsurf; enable the server in the MCP panel if needed." }
        "vscode"         { "Reload VS Code; start the server from .vscode/mcp.json." }
        "claude"         { "Restart Claude Code in this repo; run /appknox:triage or /appknox:fix." }
    }
}

# Presence heuristics: a CLI on PATH, or the client's config dir.
function Test-ClientPresent($client) {
    switch ($client) {
        "cursor"         { (Test-Path "$env:USERPROFILE\.cursor") -or (Get-Command cursor -ErrorAction SilentlyContinue) }
        "claude-desktop" { Test-Path "$env:APPDATA\Claude" }
        "codex"          { (Get-Command codex -ErrorAction SilentlyContinue) -or (Test-Path "$env:USERPROFILE\.codex") }
        "copilot"        { (Get-Command copilot -ErrorAction SilentlyContinue) -or (Test-Path "$env:USERPROFILE\.copilot") }
        "windsurf"       { (Test-Path "$env:USERPROFILE\.codeium\windsurf") -or (Get-Command windsurf -ErrorAction SilentlyContinue) }
        "vscode"         { (Get-Command code -ErrorAction SilentlyContinue) -or (Test-Path "$env:USERPROFILE\.vscode") }
        "claude"         { (Get-Command claude -ErrorAction SilentlyContinue) -or (Test-Path "$env:USERPROFILE\.claude") }
        default          { $false }
    }
}

# ---- 1. prerequisites -------------------------------------------------------
Write-Step "Checking prerequisites"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Info "uv (the Python package manager) is not installed."
    $reply = Read-Host "  Install it now from https://astral.sh/uv? [Y/n]"
    if ($reply -match "^[Nn]") { Die "uv is required. Install it (https://docs.astral.sh/uv/) and re-run." }
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    # uv installs to %USERPROFILE%\.local\bin; make sure it's on PATH now.
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { Die "uv install finished but 'uv' isn't on PATH. Open a new shell and re-run." }
}
Write-Info "OK uv found: $($uv.Source)"

# ---- 2. sync dependencies ---------------------------------------------------
Write-Step "Installing dependencies (uv sync)"
Push-Location $RepoDir
try { uv sync } finally { Pop-Location }
Write-Info "OK Dependencies installed"

# ---- 3. choose clients ------------------------------------------------------
$Selected = @()
$ShowGeneric = $false

if ($Clients.Count -gt 0) {
    foreach ($c in $Clients) {
        if ($AllClients -notcontains $c) { Die "Unknown client '$c'. Choose from: $($AllClients -join ', ')" }
        $Selected += $c
    }
} else {
    Write-Step "Detecting MCP-capable clients on your system"
    $Detected = @($AllClients | Where-Object { Test-ClientPresent $_ })

    if ($Detected.Count -eq 0) {
        Write-Warn "None detected automatically."
        $ShowGeneric = $true
    } else {
        Write-Info "Appknox detected these on your system:"
        for ($i = 0; $i -lt $Detected.Count; $i++) {
            Write-Host ("    {0}) {1}" -f ($i + 1), (Get-ClientLabel $Detected[$i]))
        }
        Write-Info "Select which to install the MCP into - space-separated numbers,"
        Write-Info "'a' for all detected, or 'm' for manual/generic steps (any other client)."
        $answer = Read-Host "  select"
        foreach ($tok in ($answer -split '\s+' | Where-Object { $_ })) {
            if ($tok -in @("a", "A", "all")) {
                $Selected = $Detected
            } elseif ($tok -in @("m", "M", "manual")) {
                $ShowGeneric = $true
            } elseif ($tok -match '^\d+$' -and [int]$tok -ge 1 -and [int]$tok -le $Detected.Count) {
                $Selected += $Detected[[int]$tok - 1]
            } else {
                Write-Warn "Ignoring '$tok' (not a number/a/m)."
            }
        }
    }
}

$Selected = @($Selected | Select-Object -Unique)

if ($Selected.Count -eq 0 -and -not $ShowGeneric) {
    Die "Nothing selected. Re-run and pick at least one client (or 'm' for manual steps)."
}

# ---- 4. credentials (only if we're writing at least one config) -------------
$BaseUrl = if ($env:APPKNOX_BASE_URL) { $env:APPKNOX_BASE_URL } else { $DefaultBaseUrl }
if ($Selected.Count -gt 0) {
    Write-Step "Credentials"
    if (-not $env:APPKNOX_ACCESS_TOKEN) {
        Write-Info "Format: <Access Key ID>:<Secret Access Key>  (input hidden)"
        $secure = Read-Host "  token" -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $env:APPKNOX_ACCESS_TOKEN = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if (-not $env:APPKNOX_ACCESS_TOKEN) { Die "No access token provided." }

    if (-not $env:APPKNOX_BASE_URL) {
        $reply = Read-Host "  base URL [$DefaultBaseUrl]"
        $BaseUrl = if ($reply) { $reply } else { $DefaultBaseUrl }
    }
    Write-Info "OK Using base URL: $BaseUrl"
}

# ---- 5. write each selected client's config ---------------------------------
# Project-scoped configs (claude/.mcp.json, vscode/.vscode/mcp.json) hold the
# token in the CURRENT repo - keep them out of git.
function Add-Gitignored($entry) {
    if (-not (Test-Path (Join-Path $PWD ".git"))) { return }
    $gi = Join-Path $PWD ".gitignore"
    $already = (Test-Path $gi) -and (Select-String -Path $gi -Pattern ([regex]::Escape($entry)) -SimpleMatch -Quiet)
    if (-not $already) {
        Add-Content -Path $gi -Value $entry
        Write-Info "OK Added '$entry' to .gitignore (holds your token)"
    }
}

# Claude Code also gets this as a plugin (marketplace-installed at user scope),
# not just an MCP entry: the plugin bundles the server's .mcp.json AND the
# slash commands + fixer agent, so it works from any repo afterward - a plain
# .mcp.json entry alone (below) only works in the one repo you write it to.
# Commands are namespaced /appknox:<name> - the plugin system always prefixes
# <plugin>:<command>, no opt-out, so that's the canonical naming everywhere.
function Install-ClaudePlugin {
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        Write-Warn "claude CLI not found - skipping plugin install (commands/agent won't be available)."
        return
    }
    claude plugin marketplace add $RepoDir --scope user | Out-Null
    claude plugin install appknox@appknox -y | Out-Null
    Write-Info "OK Installed the appknox plugin (slash commands + fixer agent, user scope)"
    Write-Warn "The plugin's MCP entry reads `$env:APPKNOX_ACCESS_TOKEN/`$env:APPKNOX_BASE_URL"
    Write-Warn "at launch - set them as user env vars to use it outside this repo, or rely"
    Write-Warn "on the .mcp.json below (token baked in, this repo only)."
}

foreach ($Client in $Selected) {
    Write-Step "Configuring $(Get-ClientLabel $Client)"
    uv run --directory $RepoDir python "$RepoDir\scripts\configure_mcp.py" `
        --client $Client --repo $RepoDir --base-url $BaseUrl --cwd $PWD
    if ($Client -eq "claude") { Add-Gitignored ".mcp.json"; Install-ClaudePlugin }
    if ($Client -eq "vscode") { Add-Gitignored ".vscode/mcp.json" }
    Write-Info "-> $(Get-ClientHint $Client)"
}

# ---- 6. generic / manual steps for unknown clients --------------------------
if ($ShowGeneric) {
    Write-Step "Manual setup (any other MCP client)"
    Write-Host @"
  Add this server to the client's MCP config. JSON clients use the key
  "mcpServers"; put your real token in place of the placeholder:

    "appknox": {
      "command": "uv",
      "args": ["run", "--directory", "$RepoDir", "appknox-mcp"],
      "env": {
        "APPKNOX_ACCESS_TOKEN": "<Access Key ID>:<Secret Access Key>",
        "APPKNOX_BASE_URL": "$BaseUrl"
      }
    }

  - VS Code:  key is "servers" and the entry needs  "type": "stdio"
  - Codex:    ~/.codex/config.toml - env vars go under a NESTED
              [mcp_servers.appknox.env] table (see README -> Manual configuration)
  - Copilot CLI: ~/.copilot/mcp-config.json - entry needs "type": "local" and
              "tools": ["*"] (see README -> Manual configuration)
"@
}

# ---- 7. done ----------------------------------------------------------------
Write-Step "Done"
if ($Selected.Count -gt 0) {
    Write-Info "Configured: $($Selected -join ', ')"
    Write-Info "From inside an app repo, ask the agent to find & fix vulnerabilities."
    Write-Info "Claude Code: /appknox:triage (browse+fix all) or /appknox:fix <analysis_id> (one vuln)."
    Write-Info "Other clients: just ask, e.g. `"fix Appknox analysis 405 in this repo`"."
    Write-Info "To remove later: .\scripts\uninstall.ps1"
}
