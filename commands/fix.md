---
description: Fix Appknox KnoxIQ vulnerabilities by analysis ID, "all", or a severity/exploitability range, verifying each with its PoC
argument-hint: "<analysis_id | all | severity | exploitability-range> [file_id]"
---

# Appknox Fix

Run from inside the app's repository. Unlike `/appknox:triage` (which lists
everything and asks what to fix), this takes the selection **as an argument** and
runs the workflow's FIX + VERIFY LOCALLY step straight away, leaving changes
staged — see the `appknox` MCP server's instructions for the full workflow and
its HAND OFF step. This file adds only the Claude-Code-specific parts: argument
mapping, progress-line formatting, and parallel sub-agent dispatch.

Arguments:
- `$1` — **selection** (required), resolved per the workflow's SELECT step: a
  single **analysis_id**, `all`, a **severity** (or comma list, e.g.
  `critical,high`), or an **exploitability level** (`highly exploitable`,
  `high exploitability`, `medium exploitability`, ... — a shorter scale than
  severity's, topping out at High, not Critical).
- `$2` — **file_id** (optional): feeds the workflow's RESOLVE step. Omitted ->
  resolve from the repo (see the workflow's IDENTIFIER DETECTION).

Print each step's status line exactly (`⏳` working, `✓` success, `✗` failure).

## Resolve, check readiness, select

Follow the workflow's RESOLVE and CHECK READINESS steps using `$2`. Then resolve
`$1`: if it's a single number, skip straight to `analysis_ids = [$1]`; otherwise
follow the workflow's SELECT matching rules against `list_analyses(file_id,
min_risk=1)`. No match -> print `✗ No findings match "<$1>" on build #<file_id>`
and stop.

## Fix + verify (Claude Code addition: parallel sub-agents)

Follow the workflow's FIX + VERIFY LOCALLY step per finding. When fixing more
than one finding, prefer dispatching one `appknox-fixer` sub-agent per finding —
sequentially for findings sharing a file, concurrently otherwise (never two
agents on the same file at once). Each sub-agent's prompt must include:
`file_id`, `analysis_id`, that finding's `developer_prompt`/`remediation`/`poc`/
vulnerability name/CWE, **and the workflow's step 5b (verify locally) text
verbatim** — the sub-agent has no MCP connection and can't read it itself.

## Report & hand off

Summarise per finding: analysis id + name, root cause (one line), files changed,
PoC result. Then follow the workflow's HAND OFF step — do not build, upload, or
commit. Once rebuilt: `/appknox:upload <binary-path>` then `/appknox:verify`.
