"""Client (SDK) for the Appknox public API.

The single place that knows the API: base URL, auth, error handling, pagination,
and one named method per endpoint. MCP tools call these methods — they never see
a URL, header, or token — so any API change is contained here.
"""

from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from appknox_mcp.models import (
    Analysis,
    File,
    KnoxIQFinding,
    Project,
    Submission,
    UploadHandshake,
)

_V1 = "/api/public_api/v1"


class AppknoxAPIError(RuntimeError):
    """Raised when a request to the Appknox public API fails."""


def _next_page_params(next_url: str) -> dict[str, str]:
    """Extract the pagination query params from a DRF ``next`` link."""
    query = urlparse(next_url).query
    return {key: values[0] for key, values in parse_qs(query).items()}


class AppknoxClient:
    """Async SDK for the Appknox public API — one method per endpoint, auth built in."""

    def __init__(
        self,
        base_url: str,
        access_token: str,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
            transport=transport,
        )

    # -- Files ---------------------------------------------------------------

    async def get_file(self, file_id: int) -> File:
        """Fetch a file's detail (identity, scan status, risk counts)."""
        return File.model_validate(await self._get(f"{_V1}/files/{file_id}"))

    async def list_project_files(self, project_id: int) -> list[File]:
        """List every file (build) of a project, newest ids last."""
        rows = await self._paginate(f"{_V1}/projects/{project_id}/files")
        return [File.model_validate(row) for row in rows]

    # -- Projects ------------------------------------------------------------

    async def list_projects(self, package_name: str) -> list[Project]:
        """List projects matching an app identifier (package_name / bundle id)."""
        payload = await self._get(f"{_V1}/projects", params={"package_name": package_name})
        return [Project.model_validate(row) for row in payload.get("results", [])]

    async def list_open_va_analyses(
        self, starting_after: int | None = None
    ) -> list[dict[str, Any]]:
        """One page of the open-VA listing (carries per-project KnoxIQ status)."""
        params: dict[str, Any] = {"limit": 100}
        if starting_after is not None:
            params["starting_after"] = starting_after
        payload = await self._get(f"{_V1}/projects/open_va_analyses", params=params)
        return payload.get("results", [])

    # -- Analyses / KnoxIQ findings -----------------------------------------

    async def list_analyses(self, file_id: int) -> list[Analysis]:
        """List every vulnerability analysis for a file."""
        rows = await self._paginate(f"{_V1}/files/{file_id}/analyses")
        return [Analysis.model_validate(row) for row in rows]

    async def list_knoxiq_findings(
        self, file_id: int, analysis_id: int
    ) -> list[KnoxIQFinding]:
        """List KnoxIQ findings (developer_prompt, remediation, poc, exploitability)."""
        rows = await self._paginate(
            f"{_V1}/files/{file_id}/analyses/{analysis_id}/knoxiq_findings"
        )
        return [KnoxIQFinding.model_validate(row) for row in rows]

    # -- Uploads -------------------------------------------------------------

    async def request_upload_url(self) -> UploadHandshake:
        """Request a presigned upload URL and its signed key."""
        return UploadHandshake.model_validate(await self._get(f"{_V1}/uploads"))

    async def put_to_storage(self, url: str, content: bytes) -> None:
        """PUT raw bytes to a presigned storage URL (unauthenticated — it is self-signed)."""
        async with httpx.AsyncClient(timeout=None) as storage_api_client:
            try:
                response = await storage_api_client.put(url, content=content)
                response.raise_for_status()
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                raise AppknoxAPIError("Failed to upload the binary to storage") from exc

    async def create_submission(
        self, upload_key: str, upload_key_signed: str
    ) -> Submission:
        """Confirm an upload to create a submission (triggers validation + scan)."""
        payload = await self._post(
            f"{_V1}/uploads",
            json={"upload_key": upload_key, "upload_key_signed": upload_key_signed},
        )
        return Submission.model_validate(payload)

    async def get_submission(self, submission_id: int) -> Submission:
        """Fetch a submission (carries file_id once validation completes)."""
        payload = await self._get(f"{_V1}/submission/{submission_id}")
        return Submission.model_validate(payload)

    # -- HTTP primitives -----------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("POST", path, json=json)

    async def _paginate(
        self, path: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        query: dict[str, Any] = {"limit": 100, **(params or {})}
        while True:
            payload = await self._get(path, params=query)
            results.extend(payload["results"])
            next_url = payload.get("next")
            if not next_url:
                return results
            query = _next_page_params(next_url)

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = await self._http.request(method, path, params=params, json=json)
            response.raise_for_status()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            raise AppknoxAPIError(f"{method} {path} failed") from exc
        return response.json()
