"""Tests for InternalAppknoxClient (OAuth mode: mycroft internal API → public models).

Response bodies mirror the mycroft serializers named in each fixture, which are
plain DRF ``JSONRenderer`` output (not JSON:API) with DRF ``LimitOffsetPagination``
envelopes (``count``/``next``/``previous``/``results``).
"""

import json

import httpx
import pytest

from appknox_mcp.client import AppknoxAPIError
from appknox_mcp.internal_client import InternalAppknoxClient, _rollup_knoxiq_status

ORG = 7
BASE = "https://api.test"


def _page(results: list, next_url: str | None = None) -> dict:
    """DRF rest_framework.pagination.LimitOffsetPagination envelope."""
    return {
        "count": len(results),
        "next": next_url,
        "previous": None,
        "results": results,
    }


def _me() -> dict:
    """core/serializers/me.py MeSerializer."""
    return {
        "id": 1,
        "username": "dev",
        "email": "dev@x.test",
        "default_organization": ORG,
    }


def _project(project_id: int = 3, latest_version: int | None = 12) -> dict:
    """core/serializers/project.py ProjectSerializer (subset of real fields + extras)."""
    return {
        "id": project_id,
        "uuid": "8b8f6c2e-1111-2222-3333-444455556666",
        "organization": ORG,
        "package_name": "com.x",
        "platform": 1,
        "url": "",
        "file_count": 2,
        "last_file_created_on": "2026-11-01T00:00:00Z",
        "is_api_scan_enabled": False,
        "active_profile_id": 9,
        "last_file_id": latest_version,
        "latest_version": latest_version,
        "is_manual_scan_available": True,
        "show_unknown_analysis": True,
    }


def _file(file_id: int = 12, project_id: int = 3, **overrides) -> dict:
    """core/serializers/file.py FileViewSerializer (fields the client reads + noise)."""
    row = {
        "id": file_id,
        "project": project_id,
        "profile": 9,
        "name": "App",
        "version": "1.0",
        "version_code": "10",
        "dynamic_status": 0,
        "is_static_done": True,
        "is_dynamic_done": False,
        "is_api_done": False,
        "risk_count_critical": 1,
        "risk_count_high": 2,
        "risk_count_medium": 3,
        "risk_count_low": 4,
        "risk_count_passed": 5,
        "risk_count_unknown": 6,
        "analyses": [{"id": 1, "findings": []}],
        "tags": [],
        "is_active": True,
    }
    row.update(overrides)
    return row


def _scan_status(sast=4, dast=0, api=0) -> dict:
    """knoxiq/serializers.py KnoxIQScanStatusSerializer."""
    return {"id": 12, "sast_status": sast, "dast_status": dast, "api_status": api}


def _cicd_row(analysis_id: int, **overrides) -> dict:
    """knoxiq/serializers.py KnoxIQCICDAnalysisSerializer."""
    row = {
        "id": analysis_id,
        "computed_risk": 3,
        "overridden_risk": None,
        "cvss_vector": "CVSS:3.1/AV:N",
        "cvss_base": 7.5,
        "vulnerability_id": 42,
        "vulnerability_name": "Insecure storage",
        "exploitability_score": 8.1,
        "exploitability_likelihood": 4,
        "is_knoxiq_all_fp": False,
        "needs_review": False,
    }
    row.update(overrides)
    return row


def _finding() -> dict:
    """knoxiq/serializers.py KnoxIQFindingSerializer (read fields)."""
    return {
        "id": 100,
        "finding_id": "F-0",
        "title": "Token in SharedPreferences",
        "description": "desc",
        "validation": {"verdict": "valid"},
        "remediation": {"summary": "use keystore"},
        "poc": {"verification_steps": []},
        "developer_prompt": "Fix it",
        "exploitability": {"score": 8.1},
        "request_response_pairs": None,
        "confirmed_request": None,
        "scan_type": 1,
        "scan_id": 0,
    }


class Router:
    """httpx MockTransport handler: (method, path) → (status, body); records calls."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        key = (request.method, request.url.path)
        if key not in self.routes:
            return httpx.Response(404, json={"detail": "Not found."})
        status, body = self.routes[key]
        if callable(body):
            body = body(request)
        return httpx.Response(status, json=body)

    def paths(self) -> list[str]:
        return [r.url.path for r in self.calls]


def _client(router: Router) -> InternalAppknoxClient:
    return InternalAppknoxClient(
        BASE, "oauth-tok", transport=httpx.MockTransport(router)
    )


# --- auth & org resolution ---------------------------------------------------


async def test_sends_oauth_bearer_and_caches_org():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", f"/api/organizations/{ORG}/projects"): (200, _page([_project()])),
        }
    )
    client = _client(router)
    await client.list_projects("com.x")
    await client.list_projects("com.x")
    assert all(r.headers["authorization"] == "Bearer oauth-tok" for r in router.calls)
    assert router.paths().count("/api/me") == 1


async def test_user_without_org_raises():
    router = Router(
        {("GET", "/api/me"): (200, {**_me(), "default_organization": None})}
    )
    with pytest.raises(AppknoxAPIError, match="no Appknox organization"):
        await _client(router).organization_id()


# --- files -------------------------------------------------------------------


async def test_get_file_maps_internal_shape_onto_public_model():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", "/api/v2/files/12"): (200, _file()),
            ("GET", f"/api/organizations/{ORG}/projects/3"): (200, _project()),
            ("GET", "/api/knoxiq/file/12/knoxiq_scan/status"): (200, _scan_status()),
        }
    )
    f = await _client(router).get_file(12)
    assert f.id == 12 and f.project_id == 3
    assert (f.package_name, f.platform, f.platform_display) == ("com.x", 1, "iOS")
    assert (f.sast_status, f.dast_status) == ("Completed", "Not Started")
    assert f.risk_count_untested == 6  # from risk_count_unknown
    assert f.is_last_file is True  # id == project.latest_version
    assert f.knoxiq_status == 4  # static done → SAST status


async def test_get_file_without_knoxiq_entitlement_has_no_knoxiq_status():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", "/api/v2/files/12"): (200, _file()),
            ("GET", f"/api/organizations/{ORG}/projects/3"): (
                200,
                _project(latest_version=99),
            ),
            ("GET", "/api/knoxiq/file/12/knoxiq_scan/status"): (
                403,
                {"detail": "You do not have permission to perform this action."},
            ),
        }
    )
    f = await _client(router).get_file(12)
    assert f.knoxiq_status is None
    assert f.is_last_file is False


async def test_get_file_dast_in_progress():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", "/api/v2/files/12"): (
                200,
                _file(is_static_done=False, dynamic_status=2),
            ),
            ("GET", f"/api/organizations/{ORG}/projects/3"): (200, _project()),
            ("GET", "/api/knoxiq/file/12/knoxiq_scan/status"): (
                200,
                _scan_status(sast=1),
            ),
        }
    )
    f = await _client(router).get_file(12)
    assert (f.sast_status, f.dast_status) == ("Not Started", "In Progress")
    assert f.knoxiq_status == 0  # nothing applicable → DISABLED


async def test_get_file_status_error_other_than_403_raises():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", "/api/v2/files/12"): (200, _file()),
            ("GET", f"/api/organizations/{ORG}/projects/3"): (200, _project()),
            ("GET", "/api/knoxiq/file/12/knoxiq_scan/status"): (
                500,
                {"detail": "boom"},
            ),
        }
    )
    with pytest.raises(AppknoxAPIError, match="knoxiq_scan/status failed: 500 boom"):
        await _client(router).get_file(12)


@pytest.mark.parametrize(
    "row,status,expected",
    [
        # Running SAST wins even though DAST finished.
        ({"is_static_done": True, "is_dynamic_done": True}, _scan_status(3, 4, 0), 3),
        # Latest stage wins: API over DAST over SAST.
        (
            {"is_static_done": True, "is_dynamic_done": True, "is_api_done": True},
            _scan_status(4, 4, 5),
            5,
        ),
        ({"is_static_done": True, "is_dynamic_done": True}, _scan_status(4, 5, 0), 5),
        # API_SCAN_DISABLED is dropped from the rollup (sub-feature off).
        ({"is_static_done": True, "is_api_done": True}, _scan_status(4, 0, 6), 4),
        # DAST status ignored until dynamic is done.
        ({"is_static_done": True}, _scan_status(4, 2, 0), 4),
        ({}, _scan_status(1, 0, 0), 0),
    ],
)
def test_knoxiq_status_rollup_mirrors_file_model(row, status, expected):
    assert _rollup_knoxiq_status(row, status) == expected


async def test_list_project_files_paginates_and_fills_project_fields():
    def page2(_):
        return _page([_file(10)])

    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", f"/api/organizations/{ORG}/projects/3"): (200, _project()),
            ("GET", "/api/projects/3/files"): (
                200,
                lambda req: (
                    page2(req)
                    if req.url.params.get("offset") == "1"
                    else _page(
                        [_file(12)],
                        f"{BASE}/api/projects/3/files?limit=1&offset=1",
                    )
                ),
            ),
        }
    )
    files = await _client(router).list_project_files(3)
    assert [f.id for f in files] == [12, 10]
    assert all(f.package_name == "com.x" and f.knoxiq_status is None for f in files)
    assert [f.is_last_file for f in files] == [True, False]


# --- projects ----------------------------------------------------------------


async def test_list_projects_filters_by_package_name_and_derives_platform_display():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", f"/api/organizations/{ORG}/projects"): (
                200,
                _page([_project(3), {**_project(4, None), "platform": 0}]),
            ),
        }
    )
    projects = await _client(router).list_projects("com.x")
    assert router.calls[-1].url.params["package_name"] == "com.x"
    assert [(p.id, p.platform_display, p.last_file_id) for p in projects] == [
        (3, "iOS", 12),
        (4, "Android", None),
    ]


# --- analyses / findings -----------------------------------------------------


async def test_list_analyses_maps_cicd_rows():
    router = Router(
        {
            ("GET", "/api/knoxiq/file/12/cicd_analyses"): (
                200,
                _page(
                    [
                        _cicd_row(1),
                        _cicd_row(
                            2,
                            computed_risk=-1,
                            cvss_base=None,
                            exploitability_score=None,
                            exploitability_likelihood=None,
                        ),
                    ]
                ),
            ),
        }
    )
    a1, a2 = await _client(router).list_analyses(12)
    assert (a1.computed_risk_display, a1.cvss_base) == ("High", "7.5")
    assert (a1.exploitability_score, a1.exploitability_likelihood) == (8.1, 4)
    assert a1.vulnerability_scan_types == [] and a1.cwe == []
    assert (a2.computed_risk_display, a2.cvss_base, a2.exploitability_score) == (
        "Unknown",
        "",
        None,
    )


async def test_list_knoxiq_findings_checks_analysis_belongs_to_file():
    router = Router(
        {
            ("GET", "/api/v2/files/12/analyses/1"): (200, {"id": 1}),
            ("GET", "/api/knoxiq/analyses/1/findings"): (200, _page([_finding()])),
        }
    )
    (finding,) = await _client(router).list_knoxiq_findings(12, 1)
    assert finding.finding_id == "F-0" and finding.developer_prompt == "Fix it"
    assert finding.poc == {"verification_steps": []}


async def test_list_knoxiq_findings_mismatched_file_is_404():
    router = Router(
        {("GET", "/api/knoxiq/analyses/1/findings"): (200, _page([_finding()]))}
    )
    with pytest.raises(
        AppknoxAPIError, match="/api/v2/files/99/analyses/1 failed: 404"
    ):
        await _client(router).list_knoxiq_findings(99, 1)


# --- uploads -----------------------------------------------------------------


async def test_upload_handshake_renames_file_key_fields():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            # organization/views/upload.py UploadViewSet.list → UploadSerializer
            ("GET", f"/api/organizations/{ORG}/upload_app"): (
                200,
                {
                    "url": "https://s3/put",
                    "file_key": "k-uuid",
                    "file_key_signed": "k-uuid:sig",
                },
            ),
        }
    )
    h = await _client(router).request_upload_url()
    assert (h.url, h.upload_key, h.upload_key_signed) == (
        "https://s3/put",
        "k-uuid",
        "k-uuid:sig",
    )


async def test_create_submission_posts_file_keys_with_knoxiq_requested():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            # UploadViewSet.create → serializer data + submission_id, 202.
            ("POST", f"/api/organizations/{ORG}/upload_app"): (
                202,
                {
                    "file_key": "k-uuid",
                    "file_key_signed": "k-uuid:sig",
                    "knoxiq": True,
                    "submission_id": 55,
                },
            ),
        }
    )
    sub = await _client(router).create_submission("k-uuid", "k-uuid:sig")
    assert sub.submission_id == 55
    assert json.loads(router.calls[-1].content) == {
        "file_key": "k-uuid",
        "file_key_signed": "k-uuid:sig",
        "knoxiq": True,
    }


def _submission(**overrides) -> dict:
    """core/serializers/submission.py SubmissionSerializer (read fields)."""
    row = {
        "id": 55,
        "file": None,
        "reason": "",
        "status": 4,
        "package_name": "com.x",
        "url": "",
        "source": 1,
        "status_humanized": "Validating the file",
        "created_on": "2026-11-01T00:00:00Z",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "body,file_id,error",
    [
        (_submission(), None, None),
        (_submission(file=12, status=7), 12, None),
        (_submission(status=5, reason="Invalid APK"), None, "Invalid APK"),
        (_submission(status=5, reason=""), None, "Unknown error"),
    ],
)
async def test_get_submission_maps_file_and_error(body, file_id, error):
    router = Router({("GET", "/api/submissions/55"): (200, body)})
    sub = await _client(router).get_submission(55)
    assert (sub.submission_id, sub.file_id, sub.error_reason) == (55, file_id, error)


# --- error mapping -----------------------------------------------------------


async def test_insufficient_scope_surfaces_api_detail():
    router = Router(
        {
            ("GET", "/api/me"): (200, _me()),
            ("GET", f"/api/organizations/{ORG}/upload_app"): (
                403,
                {"detail": "This OAuth token does not grant access to this endpoint."},
            ),
        }
    )
    with pytest.raises(
        AppknoxAPIError, match="upload_app failed: 403 This OAuth token"
    ):
        await _client(router).request_upload_url()


async def test_network_error_maps_to_api_error():
    def boom(request):
        raise httpx.ConnectError("refused", request=request)

    client = InternalAppknoxClient(BASE, "t", transport=httpx.MockTransport(boom))
    with pytest.raises(AppknoxAPIError, match="GET /api/me failed"):
        await client.organization_id()
