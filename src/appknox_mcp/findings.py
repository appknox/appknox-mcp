"""Tools for browsing and selecting KnoxIQ findings ahead of a fix run."""

import asyncio
from typing import Any

from appknox_mcp.app import READ_ONLY, client, mcp
from appknox_mcp.client import AppknoxAPIError
from appknox_mcp.models import Analysis

# Each finding carries remediation text and PoC steps; keep one response at a
# size directories accept (Claude's connector review: "reasonably sized").
MAX_FIX_PLAN_IDS = 10


@mcp.tool(title="Get build info", annotations=READ_ONLY)
async def get_file_info(file_id: int) -> dict[str, Any]:
    """Return a build's identity and scan summary.

    Includes package name, version, platform, project, SAST/DAST scan status,
    KnoxIQ status and risk counts by severity. Fields unrelated to
    vulnerability triage are omitted.
    """
    file = await client.get_file(file_id)
    return file.model_dump()


async def previous_file_id(file_id: int) -> int | None:
    """Return the build uploaded immediately before ``file_id`` in the same project.

    Resolves the project from the file, lists its builds, and returns the largest
    file id below ``file_id`` — file ids are monotonic, so that is the previous
    build. Returns None if this is the project's first build.
    """
    file = await client.get_file(file_id)
    if file.project_id is None:
        return None
    rows = await client.list_project_files(file.project_id)
    earlier = [row.id for row in rows if row.id < file_id]
    return max(earlier) if earlier else None


# The API sends exploitability_likelihood as a raw IntegerChoices code with no
# companion display field (unlike computed_risk/computed_risk_display) — this
# is that enum, kept in sync with mycroft's ExploitabilityEnum. Note the top
# tier here is "High", not "Critical" — a different, shorter scale than
# computed_risk's (which does have a Critical tier); don't conflate the two.
_EXPLOITABILITY_LIKELIHOOD_DISPLAY = {
    0: "Unknown",
    1: "Passed",
    2: "Low",
    3: "Medium",
    4: "High",
}


def _to_row(analysis: Analysis, include_exploitability: bool) -> dict[str, Any]:
    """Build a flat, display-ready row for one analysis."""
    likelihood = (
        _EXPLOITABILITY_LIKELIHOOD_DISPLAY.get(analysis.exploitability_likelihood)
        if analysis.exploitability_likelihood is not None
        else None
    )
    return {
        "id": analysis.id,
        "vulnerability_id": analysis.vulnerability_id,
        "vulnerability_name": analysis.vulnerability_name,
        "computed_risk": analysis.computed_risk,
        "computed_risk_display": analysis.computed_risk_display,
        "cvss_base": analysis.cvss_base,
        "scan_type": analysis.vulnerability_scan_types,
        "cwe": analysis.cwe,
        "exploitability_score": (
            analysis.exploitability_score if include_exploitability else None
        ),
        "exploitability_likelihood": likelihood if include_exploitability else None,
    }


@mcp.tool(title="List vulnerabilities", annotations=READ_ONLY)
async def list_analyses(
    file_id: int,
    min_risk: int | None = None,
    min_exploitability: float | None = None,
    include_exploitability: bool = True,
) -> list[dict[str, Any]]:
    """List the vulnerability analyses of a build, one row per analysis.

    Rows are sorted by KnoxIQ ``exploitability_score`` (highest first), then by
    severity. Each row has severity (``computed_risk``, ``computed_risk_display``),
    CVSS and CWE, and for KnoxIQ-enabled organizations ``exploitability_score``
    and ``exploitability_likelihood`` (Unknown, Passed, Low, Medium, High).

    ``min_risk`` keeps rows whose ``computed_risk`` is at or above the value
    (-1 Unknown, 0 Passed, 1 Low, 2 Medium, 3 High, 4 Critical).
    ``min_exploitability`` keeps rows whose ``exploitability_score`` is at or
    above the value. ``include_exploitability=false`` omits the two
    exploitability fields.
    """
    analyses = await client.list_analyses(file_id)
    if min_risk is not None:
        analyses = [
            a
            for a in analyses
            if (a.computed_risk if a.computed_risk is not None else -1) >= min_risk
        ]
    if min_exploitability is not None:
        analyses = [
            a for a in analyses if (a.exploitability_score or 0.0) >= min_exploitability
        ]
    # Exploitability first, severity as tiebreak — KnoxIQ's signal for what to
    # fix first (see instructions.py step 3). Sorted here, not left to each
    # client's prompt-following, so every agent gets the same priority order
    # regardless of how well it follows the free-text workflow instructions.
    analyses = sorted(
        analyses,
        key=lambda a: (
            a.exploitability_score or 0.0,
            a.computed_risk if a.computed_risk is not None else -1,
        ),
        reverse=True,
    )
    return [_to_row(a, include_exploitability) for a in analyses]


@mcp.tool(title="Prepare one fix", annotations=READ_ONLY)
async def knoxiq_prepare_fix(file_id: int, analysis_id: int) -> dict[str, Any]:
    """Return KnoxIQ's fix data for one vulnerability analysis of a build.

    Each finding in the response has ``developer_prompt`` (KnoxIQ's remediation
    guidance for this code base, written for a coding assistant),
    ``remediation``, ``poc`` (verification steps, and the evidence a still
    vulnerable build shows) and ``exploitability``.
    """
    findings = await client.list_knoxiq_findings(file_id, analysis_id)
    return {
        "file_id": file_id,
        "analysis_id": analysis_id,
        "findings": [f.model_dump() for f in findings],
    }


@mcp.tool(title="Get fix plan", annotations=READ_ONLY)
async def knoxiq_get_fix_plan(
    file_id: int, analysis_ids: list[int]
) -> list[dict[str, Any]]:
    """Return KnoxIQ's fix data for several vulnerability analyses of a build.

    Same per-finding fields as for a single analysis (remediation guidance,
    remediation, proof-of-concept verification steps, exploitability), grouped
    by ``analysis_id``. Accepts at most 10 analysis IDs per call, since each
    finding's payload is large.
    """
    analysis_ids = list(dict.fromkeys(analysis_ids))  # de-duplicate, keep order
    if len(analysis_ids) > MAX_FIX_PLAN_IDS:
        raise AppknoxAPIError(
            f"Too many analysis_ids ({len(analysis_ids)}); at most "
            f"{MAX_FIX_PLAN_IDS} per call — split them across several calls."
        )
    results = await asyncio.gather(
        *(
            client.list_knoxiq_findings(file_id, analysis_id)
            for analysis_id in analysis_ids
        )
    )
    return [
        {
            "analysis_id": analysis_id,
            "findings": [f.model_dump() for f in findings],
        }
        for analysis_id, findings in zip(analysis_ids, results, strict=True)
    ]
