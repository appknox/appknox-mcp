"""Tests for AppknoxClient (named endpoint methods, error handling, pagination)."""

import httpx
import pytest

from appknox_mcp.client import AppknoxClient, AppknoxAPIError


def _client(handler) -> AppknoxClient:
    return AppknoxClient("http://test", "tok", transport=httpx.MockTransport(handler))


async def test_get_file_returns_json() -> None:
    client = _client(lambda request: httpx.Response(200, json={"id": 5}))
    file = await client.get_file(5)
    assert file.id == 5


async def test_error_raises_appknox_api_error() -> None:
    client = _client(lambda request: httpx.Response(500, json={}))
    with pytest.raises(AppknoxAPIError):
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
