"""Client (SDK) for the Appknox *internal* API, authenticated with a user's OAuth token.

Remote (OAuth) mode's counterpart of ``client.AppknoxClient``. It has the same
method names, signatures and return models, so the tools don't change. Two
things differ:

* **Auth.** ``Authorization: Bearer <OAuth access token>`` is a DOT token
  issued to an MCP client for ``mcp:read`` / ``mcp:upload``. mycroft only
  accepts it on the handful of internal views opted into OAuth
  (``mycroft/authcore/mcp_oauth.py``'s ``OAuthEnabledMixin``). Every call
  acts as the **real user**, with their own project membership, instead of an
  org-level service account.
* **Endpoints and shapes.** These are dashboard/CLI endpoints, not the public
  API, so each method maps the internal response onto the public-API model the
  tools already use. Fields the internal API doesn't send directly are derived
  exactly the way mycroft's public serializers derive them (cited per method).
  Fields with no internal equivalent are left at their model default (``None``
  or ``[]``), never invented.

The HTTP primitives (auth header, error mapping, pagination) are inherited from
``AppknoxClient``, so error messages and retries behave identically. Every
endpoint method is overridden; ``put_to_storage`` is inherited unchanged
because it talks to the presigned storage URL, not to Appknox.
"""

import asyncio
from typing import Any

import httpx

from appknox_mcp.client import AppknoxAPIError, AppknoxClient, _error_detail
from appknox_mcp.models import (
    Analysis,
    File,
    KnoxIQFinding,
    Project,
    Submission,
    UploadHandshake,
)

# ak_vendor.enums.PlatformEnum.CHOICES. The public API's ``platform_display``
# is ``project.get_platform_display`` (PAFileSerializer / PAProjectSerializer);
# the internal ProjectSerializer only sends the raw ``platform`` int.
_PLATFORM_DISPLAY = {
    0: "Android",
    1: "iOS",
    2: "Windows",
    3: "common (meta)",
    -1: "Unknown",
}

# ak_vendor.enums.RiskEnum.CHOICES. The public API's ``computed_risk_display``
# is ``get_computed_risk_display`` (PAAnalysisSerializer); the internal
# KnoxIQCICDAnalysisSerializer sends only the raw ``computed_risk`` int.
_RISK_DISPLAY = {
    4: "Critical",
    3: "High",
    2: "Medium",
    1: "Low",
    0: "Passed",
    -1: "Unknown",
}

# ak_vendor.enums.DynamicStatusEnum.NONE: used to derive ``dast_status``.
_DYNAMIC_STATUS_NONE = 0
# ak_vendor.enums.SubmissionStatusEnum.VALIDATE_FAILED: used to derive ``error_reason``.
_SUBMISSION_VALIDATE_FAILED = 5

# mycroft knoxiq.enums.KnoxIQScanStatus, used to roll the per-scan-type
# statuses up into File.knoxiq_status (see _rollup_knoxiq_status).
_KNOXIQ_DISABLED = 0
_KNOXIQ_PENDING = 2
_KNOXIQ_RUNNING = 3
_KNOXIQ_API_SCAN_DISABLED = 6


def _label(labels: dict[int, str], code: Any) -> str:
    """Display label for an enum code; "Unknown" for null/unrecognized codes."""
    return labels.get(code, "Unknown") if isinstance(code, int) else "Unknown"


def _sast_status(row: dict[str, Any]) -> str:
    """PAFileSerializer.get_sast_status."""
    return "Completed" if row.get("is_static_done") else "Not Started"


def _dast_status(row: dict[str, Any]) -> str:
    """PAFileSerializer.get_dast_status."""
    if row.get("is_dynamic_done"):
        return "Completed"
    if row.get("dynamic_status") == _DYNAMIC_STATUS_NONE:
        return "Not Started"
    return "In Progress"


def _rollup_knoxiq_status(
    row: dict[str, Any], scan_status: dict[str, Any]
) -> int | None:
    """Reproduce ``core.File.knoxiq_status``, which the public API sends as
    ``knoxiq_status``, from the per-scan-type statuses that
    ``GET /api/knoxiq/file/{id}/knoxiq_scan/status`` returns
    (KnoxIQScanStatusSerializer: ``sast_status`` / ``dast_status`` /
    ``api_status``, from File.sast_/dast_/api_knoxiq_status).

    The mapping follows File.knoxiq_status:

    * A DAST status counts only if dynamic is done.
    * An API status counts only if the API scan is done. API_SCAN_DISABLED is
      what ``api_knoxiq_status`` reports when the rollup would drop a
      would-run prediction, so it is dropped here too.
    * An earlier stage that is still PENDING or RUNNING wins.
    * Otherwise the latest stage wins: API, then DAST, then SAST (SAST only
      once the static scan is done). If none apply, the result is DISABLED.
    """
    sast = scan_status.get("sast_status")
    dast = scan_status.get("dast_status") if row.get("is_dynamic_done") else None
    api = scan_status.get("api_status") if row.get("is_api_done") else None
    if api == _KNOXIQ_API_SCAN_DISABLED:
        api = None
    in_flight = {_KNOXIQ_PENDING, _KNOXIQ_RUNNING}
    for status, applicable in (
        (sast, bool(row.get("is_static_done"))),
        (dast, dast is not None),
        (api, api is not None),
    ):
        if applicable and status in in_flight:
            return status
    if api is not None:
        return api
    if dast is not None:
        return dast
    if row.get("is_static_done"):
        return sast
    return _KNOXIQ_DISABLED


def _to_file(
    row: dict[str, Any], project: dict[str, Any], knoxiq_status: int | None
) -> File:
    """Map a FileViewSerializer row (core/serializers/file.py) onto ``File``,
    using the PAFileSerializer derivations for the fields it lacks."""
    platform = project.get("platform")
    return File.model_validate(
        {
            "id": row["id"],
            "name": row.get("name"),
            "package_name": project.get("package_name"),
            "version": row.get("version"),
            "version_code": row.get("version_code"),
            "platform": platform,
            "platform_display": _label(_PLATFORM_DISPLAY, platform),
            "project_id": row.get("project"),
            "sast_status": _sast_status(row),
            "dast_status": _dast_status(row),
            "knoxiq_status": knoxiq_status,
            "risk_count_critical": row.get("risk_count_critical"),
            "risk_count_high": row.get("risk_count_high"),
            "risk_count_medium": row.get("risk_count_medium"),
            "risk_count_low": row.get("risk_count_low"),
            "risk_count_passed": row.get("risk_count_passed"),
            # PAFileSerializer: risk_count_untested = source "risk_count_unknown".
            "risk_count_untested": row.get("risk_count_unknown"),
            # PAFileSerializer.get_is_last_file: obj.id == project.latest_version_id.
            "is_last_file": row["id"] == project.get("latest_version"),
        }
    )


def _to_project(row: dict[str, Any]) -> Project:
    """Map a core ProjectSerializer row (core/serializers/project.py)."""
    platform = row.get("platform")
    return Project.model_validate(
        {
            **row,
            "platform_display": _label(_PLATFORM_DISPLAY, platform),
        }
    )


def _to_analysis(row: dict[str, Any]) -> Analysis:
    """Map a KnoxIQCICDAnalysisSerializer row (knoxiq/serializers.py).

    ``exploitability_score`` and ``exploitability_likelihood`` come from the
    same ``Analysis.knoxiq_exploitability_*`` properties that
    PAKnoxIQAnalysisSerializer uses: the most exploitable finding, null when
    no KnoxIQ data exists. ``cvss_base`` is a FloatField here and a CharField
    in the public API, so it is stringified to match. ``vulnerability_scan_types``
    and ``cwe`` have no equivalent on this endpoint and stay at their ``[]``
    defaults.
    """
    risk = row.get("computed_risk")
    cvss = row.get("cvss_base")
    return Analysis.model_validate(
        {
            "id": row["id"],
            "vulnerability_id": row["vulnerability_id"],
            "vulnerability_name": row.get("vulnerability_name"),
            "computed_risk": risk,
            "computed_risk_display": _label(_RISK_DISPLAY, risk),
            "cvss_base": "" if cvss is None else str(cvss),
            "exploitability_score": row.get("exploitability_score"),
            "exploitability_likelihood": row.get("exploitability_likelihood"),
        }
    )


class InternalAppknoxClient(AppknoxClient):
    """Async SDK for mycroft's internal API, authenticated as one user via OAuth.

    One instance per request/user is expected. The user's organization id is
    resolved once from ``/api/me`` and cached on the instance.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(base_url, token, timeout=timeout, transport=transport)
        self._organization_id: int | None = None
        self._org_lock = asyncio.Lock()

    # -- Identity ------------------------------------------------------------

    async def organization_id(self) -> int:
        """The user's default organization (MeSerializer.default_organization)."""
        async with self._org_lock:
            if self._organization_id is None:
                me = await self._get("/api/me")
                org_id = me.get("default_organization")
                if org_id is None:
                    raise AppknoxAPIError(
                        "GET /api/me failed: this user has no Appknox organization"
                    )
                self._organization_id = int(org_id)
            return self._organization_id

    # -- Files ---------------------------------------------------------------

    async def get_file(self, file_id: int) -> File:
        """Fetch a file's detail (identity, scan status, risk counts).

        Three calls, the last two concurrent: the file (FileViewSerializer),
        its project (for package name and platform, which the internal file
        serializer doesn't carry), and its KnoxIQ scan status. That status
        endpoint is gated by KnoxIQPermission, so orgs without KnoxIQ get a
        403. That maps to ``knoxiq_status=None``, the same as the public API,
        which only sends the field to KnoxIQ-enabled orgs.
        """
        row = await self._get(f"/api/v2/files/{file_id}")
        project, scan_status = await asyncio.gather(
            self._get_project(row["project"]),
            self._get_or_none(
                f"/api/knoxiq/file/{file_id}/knoxiq_scan/status", none_on=(403,)
            ),
        )
        knoxiq_status = (
            _rollup_knoxiq_status(row, scan_status) if scan_status is not None else None
        )
        return _to_file(row, project, knoxiq_status)

    async def list_project_files(self, project_id: int) -> list[File]:
        """List every file (build) of a project.

        Rows come newest first (ProjectFileViewset orders by ``-id``). Callers
        only take the max or min id, so the order doesn't matter. Rows carry
        no ``knoxiq_status``; use ``get_file`` for that.
        """
        project, rows = await asyncio.gather(
            self._get_project(project_id),
            self._paginate(f"/api/projects/{project_id}/files"),
        )
        return [_to_file(row, project, None) for row in rows]

    # -- Projects ------------------------------------------------------------

    async def list_projects(self, package_name: str) -> list[Project]:
        """List the user's projects matching an app identifier.

        ProjectFilter.filter_package_name matches case-insensitively exactly,
        and only applies to values longer than one character. The queryset
        (OrganizationProjectViewSet) is the user's own accessible, active
        projects.
        """
        org_id = await self.organization_id()
        rows = await self._paginate(
            f"/api/organizations/{org_id}/projects",
            params={"package_name": package_name},
        )
        return [_to_project(row) for row in rows]

    async def _get_project(self, project_id: int) -> dict[str, Any]:
        org_id = await self.organization_id()
        return await self._get(f"/api/organizations/{org_id}/projects/{project_id}")

    # -- Analyses / KnoxIQ findings -----------------------------------------

    async def list_analyses(self, file_id: int) -> list[Analysis]:
        """List the file's analyses with KnoxIQ exploitability
        (``GET /api/knoxiq/file/{id}/cicd_analyses``, the CLI's contract).

        Unlike the public API, this endpoint uses ``file.get_filtered_analyses()``.
        That hides manual-scan analyses when the project has no manual scan, and
        Unknown-risk analyses when the profile hides them, the same as the
        dashboard does.
        """
        rows = await self._paginate(f"/api/knoxiq/file/{file_id}/cicd_analyses")
        return [_to_analysis(row) for row in rows]

    async def list_knoxiq_findings(
        self, file_id: int, analysis_id: int
    ) -> list[KnoxIQFinding]:
        """List KnoxIQ findings (developer_prompt, remediation, poc, exploitability).

        The internal route is keyed by analysis alone, so the pair is first
        checked against ``GET /api/v2/files/{file_id}/analyses/{analysis_id}``
        (FileAnalysisViewSet, which is scoped to ``file.analyses``). A
        mismatched pair then 404s, as the public API's nested route does,
        instead of returning another build's findings. The default filter is
        valid findings only, as in the public API. KnoxIQFindingSerializer
        reads the same ``effective_content`` keys as PAKnoxIQFindingSerializer.
        """
        _, rows = await asyncio.gather(
            self._get(f"/api/v2/files/{file_id}/analyses/{analysis_id}"),
            self._paginate(f"/api/knoxiq/analyses/{analysis_id}/findings"),
        )
        return [KnoxIQFinding.model_validate(row) for row in rows]

    # -- Uploads -------------------------------------------------------------

    async def request_upload_url(self) -> UploadHandshake:
        """Request a presigned upload URL and its signed key.

        UploadViewSet.list returns ``{url, file_key, file_key_signed}``. The
        public API renames the last two to ``upload_key`` and
        ``upload_key_signed``.
        """
        org_id = await self.organization_id()
        payload = await self._get(f"/api/organizations/{org_id}/upload_app")
        return UploadHandshake.model_validate(
            {
                "url": payload.get("url"),
                "upload_key": payload.get("file_key"),
                "upload_key_signed": payload.get("file_key_signed"),
            }
        )

    async def create_submission(
        self, upload_key: str, upload_key_signed: str
    ) -> Submission:
        """Confirm an upload to create a submission (triggers validation + scan).

        Sends ``knoxiq: true``, the flag ``appknox upload --knoxiq`` sets.
        Without it an internal upload records KnoxIQ as not requested, and the
        whole point of this server is the KnoxIQ fix-and-verify loop. The
        public API never sends the flag. Entitlement is still enforced
        server-side (``knoxiq.tasks._should_auto_trigger``).
        """
        org_id = await self.organization_id()
        payload = await self._post(
            f"/api/organizations/{org_id}/upload_app",
            json={
                "file_key": upload_key,
                "file_key_signed": upload_key_signed,
                "knoxiq": True,
            },
        )
        return Submission.model_validate(
            {"submission_id": payload.get("submission_id")}
        )

    async def get_submission(self, submission_id: int) -> Submission:
        """Fetch a submission (carries file_id once validation completes).

        SubmissionSerializer sends ``file`` (a pk, or null while validating),
        ``status`` and ``reason``. ``error_reason`` mirrors the public
        SubmissionFileSerializer: set only for VALIDATE_FAILED, falling back
        to "Unknown error". The queryset is ``request.user.submissions``, so
        only the token holder's own uploads are visible.
        """
        payload = await self._get(f"/api/submissions/{submission_id}")
        failed = payload.get("status") == _SUBMISSION_VALIDATE_FAILED
        return Submission.model_validate(
            {
                "submission_id": payload.get("id"),
                "file_id": payload.get("file"),
                "error_reason": (
                    (payload.get("reason") or "Unknown error") if failed else None
                ),
            }
        )

    # -- HTTP primitives -----------------------------------------------------

    async def _get_or_none(
        self, path: str, none_on: tuple[int, ...]
    ) -> dict[str, Any] | None:
        """GET that maps the given status codes to ``None`` instead of raising."""
        try:
            response = await self._http.get(path)
        except httpx.RequestError as exc:
            raise AppknoxAPIError(f"GET {path} failed: {exc}") from exc
        if response.status_code in none_on:
            return None
        if response.is_error or response.is_redirect:
            raise AppknoxAPIError(
                f"GET {path} failed: {response.status_code} {_error_detail(response)}"
            )
        result: dict[str, Any] = response.json()
        return result
