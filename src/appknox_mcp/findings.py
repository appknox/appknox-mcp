"""Tools for browsing and selecting KnoxIQ findings ahead of a fix run."""

import asyncio
from typing import Any

from appknox_mcp.app import client, mcp
from appknox_mcp.models import Analysis


@mcp.tool
async def get_file_info(file_id: int) -> dict[str, Any]:
    """Fetch a file's identity and scan summary (package_name, version, platform, risk counts).

    Use this to identify the app behind a ``file_id`` and, for post-fix
    verification, to confirm a re-uploaded build is the same app — matching
    ``package_name`` and ``platform`` — before comparing analyses across the
    two files. Fields not relevant to triage are dropped from the response.
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
_EXPLOITABILITY_LIKELIHOOD_DISPLAY = {0: "Unknown", 1: "Passed", 2: "Low", 3: "Medium", 4: "High"}


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


@mcp.tool
async def list_analyses(
    file_id: int,
    min_risk: int | None = None,
    min_exploitability: float | None = None,
    include_exploitability: bool = True,
) -> list[dict[str, Any]]:
    """List all vulnerability analyses for a file (one row per analysis).

    This is the generic analyses list (the `/files/{id}/analyses` endpoint). For
    KnoxIQ-enabled orgs it already carries each analysis's highest KnoxIQ
    `exploitability` — every filter below works off that single call, no
    per-analysis fetches.

    Always sorted exploitability-first, severity as tiebreak (KnoxIQ's signal
    for what to fix first) — present rows in this order, don't re-sort by id.

    `min_risk` filters on `computed_risk` (-1 Unknown, 0 Passed, 1 Low, 2 Medium,
    3 High, 4 Critical). `min_exploitability` filters on `exploitability_score`
    (the highest KnoxIQ exploitability score among an analysis's findings). Set
    `include_exploitability=False` to drop `exploitability_score`/
    `exploitability_likelihood` from the response (e.g. for a compact risk-only
    browse of a file with many analyses) — leave it at the default otherwise,
    since exploitability is what makes the sort order meaningful.
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
            a
            for a in analyses
            if (a.exploitability_score or 0.0) >= min_exploitability
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


@mcp.tool
async def knoxiq_prepare_fix(file_id: int, analysis_id: int) -> dict[str, Any]:
    """Gather everything needed to fix ONE vulnerability, in a single call.

    This is the portable equivalent of the ``/appknox:fix`` slash command for
    non-Claude clients: give it the ``file_id`` and the ``analysis_id`` the user
    wants fixed and it returns that finding's full fix payload — ``developer_prompt``
    (the primary instruction), ``remediation``, ``poc`` (whose ``verification_steps``
    you run after the fix to confirm it), and ``exploitability``. Apply the fix,
    then run the PoC steps to confirm it before rebuilding.
    """
    findings = await client.list_knoxiq_findings(file_id, analysis_id)
    return {
        "file_id": file_id,
        "analysis_id": analysis_id,
        "findings": [f.model_dump() for f in findings],
    }


@mcp.tool
async def knoxiq_get_fix_plan(
    file_id: int, analysis_ids: list[int]
) -> list[dict[str, Any]]:
    """Fetch full KnoxIQ fix data (developer_prompt, remediation, poc) for chosen analyses.

    Call this only for the analysis IDs a user has confirmed they want fixed -
    it fetches the full finding payload, which is heavier than `list_analyses`.
    """
    results = await asyncio.gather(
        *(client.list_knoxiq_findings(file_id, analysis_id) for analysis_id in analysis_ids)
    )
    return [
        {
            "analysis_id": analysis_id,
            "findings": [f.model_dump() for f in findings],
        }
        for analysis_id, findings in zip(analysis_ids, results, strict=True)
    ]
