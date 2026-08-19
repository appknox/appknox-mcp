"""Post-fix verification: compare a re-scanned build to confirm fixes landed.

Vulnerabilities are matched across builds by ``vulnerability_id`` (stable), not by
``analysis_id`` (per-file). Gated on the new build's readiness so it never reports
"all fixed" off an incomplete scan.
"""

from typing import Any

from appknox_mcp import findings, status
from appknox_mcp.app import mcp


def _open_vuln_index(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Index still-open findings by vulnerability_id."""
    index: dict[int, dict[str, Any]] = {}
    for row in rows:
        vid = row.get("vulnerability_id")
        if vid is not None:
            index[vid] = row
    return index


async def _resolve_targets(
    vulnerability_ids: list[int] | None, old_file_id: int | None, min_risk: int
) -> dict[int, str]:
    """Return {vulnerability_id: name} for the vulns to verify (explicit ids, else old build's open set)."""
    if vulnerability_ids:
        return {vid: "" for vid in vulnerability_ids}
    if old_file_id is None:
        return {}
    old_rows = await findings.list_analyses(
        old_file_id, min_risk=min_risk, include_exploitability=False
    )
    return {
        r["vulnerability_id"]: r.get("vulnerability_name", "")
        for r in old_rows
        if r.get("vulnerability_id") is not None
    }


def _no_baseline_result(new_file_id: int) -> dict[str, Any]:
    """Result when there is no earlier build and nothing specific to check."""
    return {
        "ready": True,
        "new_file_id": new_file_id,
        "old_file_id": None,
        "resolved": [],
        "still_open": [],
        "summary": {"checked": 0, "resolved": 0, "still_open": 0},
        "message": (
            "This is the project's first build — no earlier scan to compare "
            "against. Pass vulnerability_ids or an old_file_id to verify specific "
            "fixes."
        ),
    }


def _split_targets(
    targets: dict[int, str], new_open: dict[int, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split target vulns into resolved vs still-open against the new build's open set.

    Still-open entries carry the new build's exploitability, so a fix that reduced
    exploitability without fully resolving the finding is visible, not just a flat
    "still open".
    """
    resolved: list[dict[str, Any]] = []
    still_open: list[dict[str, Any]] = []
    for vid, name in targets.items():
        row = new_open.get(vid)
        entry = {
            "vulnerability_id": vid,
            "vulnerability_name": name or (row or {}).get("vulnerability_name", ""),
        }
        if row is None:
            resolved.append(entry)
        else:
            entry["computed_risk_display"] = row.get("computed_risk_display")
            entry["exploitability_score"] = row.get("exploitability_score")
            entry["exploitability_likelihood"] = row.get("exploitability_likelihood")
            still_open.append(entry)
    return resolved, still_open


@mcp.tool
async def knoxiq_verify_fixes(
    new_file_id: int,
    vulnerability_ids: list[int] | None = None,
    old_file_id: int | None = None,
    min_risk: int = 1,
) -> dict[str, Any]:
    """Confirm fixes landed by checking a re-scanned build for the vulnerabilities you fixed.

    Run this after re-uploading a fixed build (see ``upload_binary``) once its scan
    completes. Pass ``new_file_id`` (the re-scanned build); by default it compares
    against the **previous build** in the same project. To scope it instead, pass
    EITHER the ``vulnerability_ids`` you fixed OR an explicit ``old_file_id``. A
    vulnerability counts as resolved when it is no longer open (risk >= ``min_risk``)
    in the new build; findings are matched across builds by ``vulnerability_id``. If
    the new build's scan/KnoxIQ has not completed yet this returns ``ready: false``
    with a message instead of a premature "all fixed". When comparing against an old
    build, ``new_or_regressed`` lists vulns open in the new build that were not open
    before. ``still_open`` entries carry the new build's ``exploitability_score``/
    ``exploitability_likelihood``, so a fix that lowered exploitability without
    fully resolving the finding is visible instead of reading as a no-op.
    """
    scan_status = await status.knoxiq_get_scan_status(new_file_id)
    if not scan_status["ready"]:
        return {
            "ready": False,
            "new_file_id": new_file_id,
            "scan_status": scan_status,
            "message": scan_status["message"],
        }

    # Neither a target set nor a baseline given: default to the previous build.
    if old_file_id is None and not vulnerability_ids:
        old_file_id = await findings.previous_file_id(new_file_id)
        if old_file_id is None:
            return _no_baseline_result(new_file_id)

    new_open = _open_vuln_index(
        await findings.list_analyses(
            new_file_id, min_risk=min_risk, include_exploitability=True
        )
    )
    targets = await _resolve_targets(vulnerability_ids, old_file_id, min_risk)
    resolved, still_open = _split_targets(targets, new_open)
    result: dict[str, Any] = {
        "ready": True,
        "new_file_id": new_file_id,
        "old_file_id": old_file_id,
        "resolved": resolved,
        "still_open": still_open,
        "summary": {
            "checked": len(targets),
            "resolved": len(resolved),
            "still_open": len(still_open),
        },
    }
    if old_file_id is not None:
        result["new_or_regressed"] = [
            {
                "vulnerability_id": vid,
                "vulnerability_name": row.get("vulnerability_name", ""),
                "computed_risk_display": row.get("computed_risk_display"),
                "exploitability_score": row.get("exploitability_score"),
                "exploitability_likelihood": row.get("exploitability_likelihood"),
            }
            for vid, row in new_open.items()
            if vid not in targets
        ]
    if not targets:
        result["message"] = (
            "Nothing to compare: the baseline build had no open findings at or "
            "above the risk threshold."
        )
    return result
