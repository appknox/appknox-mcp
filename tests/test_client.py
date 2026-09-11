"""Tests for AppknoxClient (named endpoint methods, error handling, pagination)."""

import httpx
import pytest

from appknox_mcp.client import AppknoxClient, AppknoxAPIError, _ensure_https


def _client(handler) -> AppknoxClient:
    return AppknoxClient("https://test", "tok", transport=httpx.MockTransport(handler))


def test_ensure_https_leaves_https_url_unchanged() -> None:
    assert _ensure_https("https://sherlock-mcp.staging.appknox.io") == (
        "https://sherlock-mcp.staging.appknox.io"
    )


def test_ensure_https_adds_scheme_to_bare_host() -> None:
    """The common mistake: pasting just the domain, no scheme at all."""
    assert _ensure_https("sherlock-mcp.staging.appknox.io") == (
        "https://sherlock-mcp.staging.appknox.io"
    )


def test_ensure_https_upgrades_http() -> None:
    """Every Appknox environment redirects http:// away at the infra layer —
    fix it silently instead of letting the first real request hit that."""
    assert _ensure_https("http://sherlock-mcp.staging.appknox.io") == (
        "https://sherlock-mcp.staging.appknox.io"
    )


def test_ensure_https_replaces_other_schemes() -> None:
    assert _ensure_https("ftp://sherlock-mcp.staging.appknox.io") == (
        "https://sherlock-mcp.staging.appknox.io"
    )


async def test_client_actually_sends_requests_to_the_normalized_url() -> None:
    """Wiring check: AppknoxClient must call _ensure_https, not just have it
    available — this catches forgetting to use it in __init__."""
    seen_urls = []
    client = AppknoxClient(
        "sherlock-mcp.staging.appknox.io",
        "tok",
        transport=httpx.MockTransport(
            lambda request: seen_urls.append(str(request.url)) or httpx.Response(200, json={"id": 5})
        ),
    )
    await client.get_file(5)
    assert seen_urls[0].startswith("https://sherlock-mcp.staging.appknox.io")


async def test_get_file_returns_json() -> None:
    client = _client(lambda request: httpx.Response(200, json={"id": 5}))
    file = await client.get_file(5)
    assert file.id == 5


async def test_error_raises_appknox_api_error() -> None:
    client = _client(lambda request: httpx.Response(500, json={}))
    with pytest.raises(AppknoxAPIError):
        await client.get_file(5)


async def test_error_message_surfaces_status_and_detail_key() -> None:
    client = _client(lambda request: httpx.Response(401, json={"detail": "Invalid token"}))
    with pytest.raises(AppknoxAPIError, match="401.*Invalid token"):
        await client.get_file(5)


async def test_error_message_surfaces_error_key() -> None:
    client = _client(lambda request: httpx.Response(404, json={"error": "Not Found (404)"}))
    with pytest.raises(AppknoxAPIError, match="404.*Not Found"):
        await client.get_file(5)


async def test_error_message_falls_back_to_raw_body_for_non_json() -> None:
    client = _client(lambda request: httpx.Response(502, text="Bad Gateway"))
    with pytest.raises(AppknoxAPIError, match="502.*Bad Gateway"):
        await client.get_file(5)


async def test_error_message_surfaces_redirect_location() -> None:
    """A redirect's body is normally empty — the Location header is the only
    thing that actually explains it (trailing slash, scheme mismatch, moved
    host, ...); without this the error is just a bare, undiagnosable 301/302."""
    client = _client(
        lambda request: httpx.Response(
            301, headers={"Location": "/api/public_api/v1/files/5/"}, text=""
        )
    )
    with pytest.raises(AppknoxAPIError, match=r"301 redirected to /api/public_api/v1/files/5/"):
        await client.get_file(5)


async def test_error_message_handles_redirect_with_no_location_header() -> None:
    client = _client(lambda request: httpx.Response(301, text=""))
    with pytest.raises(AppknoxAPIError, match="redirected \\(no Location header\\)"):
        await client.get_file(5)


async def test_request_error_surfaces_exception_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("connection timed out")

    client = _client(handler)
    with pytest.raises(AppknoxAPIError, match="connection timed out"):
        await client.get_file(5)


async def test_list_projects_returns_results() -> None:
    client = _client(
        lambda request: httpx.Response(200, json={"results": [{"id": 1}], "next": None})
    )
    projects = await client.list_projects("com.x")
    assert [p.id for p in projects] == [1]


async def test_create_submission_posts_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(202, json={"submission_id": 7})

    client = _client(handler)
    submission = await client.create_submission("k", "k:sig")
    assert submission.submission_id == 7


async def test_list_project_files_follows_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        after = request.url.params.get("starting_after", "0")
        if after == "0":
            return httpx.Response(
                200,
                json={"results": [{"id": 1}], "next": "http://test/p?starting_after=1"},
            )
        return httpx.Response(200, json={"results": [{"id": 2}], "next": None})

    client = _client(handler)
    rows = await client.list_project_files(3)
    assert [r.id for r in rows] == [1, 2]
