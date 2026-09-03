<#
.SYNOPSIS
    Remove the Appknox KnoxIQ MCP server from an MCP client.

.DESCRIPTION
    Windows PowerShell counterpart to uninstall.sh — same flow, same
    configure_mcp.py backend.

.EXAMPLE
    .\scripts\uninstall.ps1 cursor

.NOTES
    client in cursor | codex | copilot | windsurf | vscode | claude | claude-desktop
    (prompted if omitted)

    Only the `appknox` server entry is deleted; any other servers in the config
    are left untouched. No credentials are read or needed. This does not
    uninstall uv or the repo - just the client's pointer to this server.
#>

param(
    [string]$Client = ""
)

$ErrorActionPreference = "Stop"

$RepoDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ValidClients = @("cursor", "codex", "copilot", "windsurf", "vscode", "claude", "claude-desktop")

function Write-Info($msg) { Write-Host "  $msg" }
function Write-Step($msg) { Write-Host "`n▸ $msg" -ForegroundColor White }
function Die($msg) { Write-Host "✗ $msg" -ForegroundColor Red; exit 1 }

if (-not $Client) {
    Write-Step "Which client?"
    Write-Info "Options: $($ValidClients -join ' ')"
    $Client = Read-Host "  client"
}
if ($ValidClients -notcontains $Client) {
    Die "Unknown client '$Client'. Choose one of: $($ValidClients -join ' ')"
}

Write-Step "Removing appknox from $Client config"
# Prefer uv (matches install), but fall back to a bare python so uninstall works
# even if the environment is half torn down.
if (Get-Command uv -ErrorAction SilentlyContinue) {
    uv run --directory $RepoDir python "$RepoDir\scripts\configure_mcp.py" `
        --client $Client --cwd $PWD --remove
} else {
    python "$RepoDir\scripts\configure_mcp.py" --client $Client --cwd $PWD --remove
}

if ($Client -eq "claude" -and (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Step "Removing the appknox plugin (slash commands + fixer agent)"
    claude plugin uninstall appknox@appknox -y 2>&1 | Out-Null
    claude plugin marketplace remove appknox 2>&1 | Out-Null
    Write-Info "OK Plugin and marketplace entry removed (user scope)"
}

Write-Step "Done"
Write-Info "Restart $Client so it drops the server and its tools."
