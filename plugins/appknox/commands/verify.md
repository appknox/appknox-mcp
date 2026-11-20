---
description: Compare a re-scanned Appknox build against the previous build to confirm which vulnerabilities are now resolved
argument-hint: "[new_file_id] [old_file_id | vulnerability_ids]"
---

# Appknox Verify

Runs the workflow's step 7 (RE-SCAN, ground truth) — confirms your fixes landed
by calling `knoxiq_verify_fixes`; see its docstring and the `appknox` MCP
server's instructions for exact comparison semantics (resolved / still_open /
new_or_regressed, exploitability carried on still_open). This file adds only
argument mapping and progress-line formatting.

Arguments (all optional):
- `$1` — **new_file_id**: the re-scanned build (from `/appknox:upload`). Omitted
  -> resolve the repo's latest build (workflow's IDENTIFIER DETECTION).
- `$2` — either an **old_file_id** to compare against, or a comma-separated list
  of **vulnerability_ids** you fixed. Omitted -> the previous build is used.

Print each step's status line exactly (`⏳` working, `✓` success, `✗` failure).

## Resolve & check readiness

If `$1` is given, use it as `new_file_id`; otherwise resolve it from the repo.
Call `knoxiq_get_scan_status` first for a clean status line (`knoxiq_verify_fixes`
also gates on this internally) — if not ready, print `⏳ <message>` and stop;
never report "resolved" off an incomplete scan.

## Compare & report

Call `knoxiq_verify_fixes(new_file_id, old_file_id=<$2> or vulnerability_ids=<$2>)`.
Lead with the build pair, then the verdict:

`Comparing #<new_file_id> against #<old_file_id>`

```
✓ Resolved (r/checked):
    <vulnerability_name>   (vuln #<vulnerability_id>)
✗ Still open (s/checked):
    <vulnerability_name>   <computed_risk_display>   <exploitability_likelihood>   (vuln #<vulnerability_id>)
```

List `new_or_regressed` under `⚠ New or regressed:` if non-empty. Close with
`<r> resolved · <s> still open`, and if any remain, suggest `/appknox:fix
<selection>` then rebuild → `/appknox:upload` → `/appknox:verify` again.
