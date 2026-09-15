"""Scan- and KnoxIQ-readiness checks for a build, with actionable messages.

The file-detail endpoint reports SAST/DAST status, and — for KnoxIQ-enabled
orgs — a ``knoxiq_status`` code alongside them. This turns that code into a
clear message explaining *why* there are no KnoxIQ findings yet, instead of
showing an empty list.
"""

from typing import Any

from appknox_mcp.app import client, mcp

# KnoxIQScanStatus codes mirrored from mycroft (knoxiq/enums.py).
KNOXIQ_LEGACY = -1
KNOXIQ_DISABLED = 0
KNOXIQ_NOT_TRIGGERED = 1
KNOXIQ_PENDING = 2
KNOXIQ_RUNNING = 3
KNOXIQ_COMPLETED = 4
KNOXIQ_ERRORED = 5

_KNOXIQ_STATUS_LABEL = {
    KNOXIQ_LEGACY: "Legacy",
    KNOXIQ_DISABLED: "Disabled",
    KNOXIQ_NOT_TRIGGERED: "Not Triggered",
    KNOXIQ_PENDING: "Pending",
    KNOXIQ_RUNNING: "Running",
    KNOXIQ_COMPLETED: "Completed",
    KNOXIQ_ERRORED: "Errored",
}

# Actionable message per non-ready KnoxIQ status (COMPLETED is handled separately).
_KNOXIQ_MESSAGE = {
    KNOXIQ_LEGACY: (
        "This build predates KnoxIQ being enabled for your organization (Legacy), "
        "so it has no KnoxIQ enrichment. Upload a fresh build to get findings."
    ),
    KNOXIQ_DISABLED: (
        "KnoxIQ is not enabled for this build. Enable KnoxIQ for your organization "
        "in the Appknox dashboard (for CI/SDK uploads, also turn on auto-execute "
        "on CI/CD upload), then upload a build."
    ),
    KNOXIQ_NOT_TRIGGERED: "KnoxIQ has not been triggered for this build yet.",
    KNOXIQ_PENDING: (
        "KnoxIQ analysis is queued (pending). Findings appear once it completes — "
        "check back shortly."
    ),
    KNOXIQ_RUNNING: (
        "KnoxIQ analysis is still running. Vulnerabilities and exploitability will "
        "be available once it completes — check back shortly."
    ),
    KNOXIQ_ERRORED: (
        "The KnoxIQ analysis errored for this build. Re-run the scan from the "
        "Appknox dashboard, or contact Appknox support."
    ),
}


def _scan_completed(sast_status: str | None, dast_status: str | None) -> bool:
    """True if either the static or dynamic scan has finished."""
    return "Completed" in (sast_status, dast_status)


def _readiness(
    sast_status: str | None, dast_status: str | None, code: int | None
) -> tuple[bool, str]:
    """Return (ready, message) for a build's KnoxIQ readiness.

    Ready only when findings are available: KnoxIQ COMPLETED, or — when the org
    isn't KnoxIQ-enabled and ``code`` is absent — a completed scan.
    """
    if code == KNOXIQ_COMPLETED:
        return True, "KnoxIQ analysis is complete — findings are ready."
    if code is not None:
        return False, _KNOXIQ_MESSAGE.get(code, f"KnoxIQ status code {code}.")
    if not _scan_completed(sast_status, dast_status):
        return False, (
            f"The security scan has not completed yet "
            f"(SAST: {sast_status}, DAST: {dast_status}). KnoxIQ findings become "
            "available after the scan finishes — check back shortly."
        )
    return True, (
        "Scan is complete. (KnoxIQ status could not be confirmed for this build; "
        "if findings come back empty, KnoxIQ may not be enabled for it.)"
    )


@mcp.tool
async def knoxiq_get_scan_status(file_id: int) -> dict[str, Any]:
    """Report whether a build's scan and KnoxIQ analysis are ready, with a clear message.

    Call this right after resolving a ``file_id`` and before listing findings: it
    tells you (and the user) whether KnoxIQ findings are actually available yet, or
    why they are not — scan still running, KnoxIQ not enabled for the organization,
    the build predates KnoxIQ, etc. ``ready`` is true only when findings are
    available; when it is false, show ``message`` to the user and do NOT present an
    empty findings list as "no vulnerabilities found". Also used by
    ``knoxiq_verify_fixes`` to avoid declaring fixes confirmed before the re-scan.
    """
    file = await client.get_file(file_id)
    code = file.knoxiq_status
    label = _KNOXIQ_STATUS_LABEL.get(code) if code is not None else None
    ready, message = _readiness(file.sast_status, file.dast_status, code)
    return {
        "file_id": file_id,
        "package_name": file.package_name,
        "project_id": file.project_id,
        "platform_display": file.platform_display,
        "sast_status": file.sast_status,
        "dast_status": file.dast_status,
        "knoxiq_status": label,
        "knoxiq_status_code": code,
        "ready": ready,
        "message": message,
    }
