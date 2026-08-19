---
description: Resolve this repo's app on Appknox, list KnoxIQ vulnerabilities, and fix the ones you pick
argument-hint: "[file_id | package_name] [min_risk]"
---

# Appknox Triage & Fix

Run from inside the app's repository. Follows the Appknox KnoxIQ workflow (the
`appknox` MCP server's instructions — steps 1–6) end to end: resolve, check
readiness, triage, select, then fix + verify the ones you pick. This file adds
only what's specific to Claude Code: argument mapping, progress-line formatting,
and parallel sub-agent dispatch — the workflow itself, including the exact
selection-matching rules, lives in the server's instructions, not here.

Arguments (all optional), mapped onto the workflow:
- `$1` — feeds step 1 (RESOLVE): a **file_id** (numeric) to use a specific build,
  or a **package_name** (contains a dot) to override auto-detection. Omitted ->
  auto-detect from the repo and use the latest scanned build.
- `$2` — feeds step 3 (TRIAGE): **min_risk** floor (`-1` Unknown … `4` Critical).
  Default **1** (Low and above), so Passed/Untested are hidden.

Print each step's status line **exactly** as shown (a leading `⏳` while working,
`✓` on success, `✗` on failure) so the run reads as a clear progress log — this
formatting is a Claude Code convention, not part of the workflow itself.

## Steps 1–3 — Resolve, check readiness, triage

Follow the workflow's RESOLVE / CHECK READINESS / TRIAGE steps using `$1`/`$2`
as above. Emit a `⏳`/`✓`/`✗` line per step; on any stop condition (bad resolve,
not-ready scan), print `✗ <message>` and stop.

## Step 4 — Select

Follow the workflow's SELECT step as-is: suggest the exploitability-led default,
wait for the user's reply, resolve it into `analysis_id`s per the workflow's
matching rules. Ambiguous or empty match -> ask, don't guess.

## Step 5 — Fix + verify (Claude Code addition: parallel sub-agents)

Follow the workflow's FIX + VERIFY LOCALLY step per finding, with this
Claude-Code-specific execution detail: dispatch one `appknox-fixer` sub-agent per
finding — pass it `file_id`, `analysis_id`, that finding's `developer_prompt`,
`remediation`, `poc`, vulnerability name, CWE, **and the workflow's step 5b
(verify locally) text verbatim** (the sub-agent has no MCP connection and can't
read it itself); it fixes and PoC-verifies per that text, then reports back.
Findings sharing a file: dispatch **sequentially**. Findings whose files don't
overlap: dispatch **concurrently**, grouped so no two agents ever touch the same
file. Print `⚙ Fixing <k> finding(s) <sequentially|in parallel>…`.

## Step 6 — Report & hand off

Print a summary including each fixer's PoC result:
```
✓ Fixed (k/n):
    #405  Network Security Misconfiguration   Critical   PoC: passed
    #338  Insecure Data Storage               High       PoC: manual (needs device)
✗ Not fixed (n-k):
    #408  Janus Vulnerability                 High   — <reason>
```
Then follow the workflow's HAND OFF step. Point to `/appknox:upload` and
`/appknox:verify` for the re-scan steps — do not build, upload, or commit here.
