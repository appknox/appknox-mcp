"""Tests for resolve_latest_file (package_name -> latest Appknox file_id)."""

from typing import Any

import pytest

from appknox_mcp import resolve
from appknox_mcp.client import AppknoxAPIError
from appknox_mcp.models import Project


class _FakeProjectsClient:
    """Returns a fixed project list for the list_projects lookup."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self._results = results
        self.calls: list[str] = []

    async def list_projects(self, package_name: str) -> list[Project]:
        self.calls.append(package_name)
        return [Project.model_validate(r) for r in self._results]


@pytest.fixture
def fake_projects(monkeypatch: pytest.MonkeyPatch):
    def _install(results: list[dict[str, Any]]) -> _FakeProjectsClient:
        client = _FakeProjectsClient(results)
        monkeypatch.setattr(resolve, "client", client)
        return client

    return _install


async def test_resolve_returns_latest_file(fake_projects) -> None:
    client = fake_projects(
        [{
            "id": 1,
            "package_name": "com.appknox.mfva",
            "platform": 0,
            "platform_display": "Android",
            "last_file_id": 5,
            "file_count": 3,
        }]
    )

    out = await resolve.resolve_latest_file("com.appknox.mfva")

    assert out["file_id"] == 5
    assert out["project_id"] == 1
    assert out["platform_display"] == "Android"
    assert client.calls == ["com.appknox.mfva"]


async def test_resolve_no_project_raises(fake_projects) -> None:
    fake_projects([])
    with pytest.raises(AppknoxAPIError, match="No Appknox project"):
        await resolve.resolve_latest_file("com.absent.app")


async def test_multiple_matches_uses_newest_build(fake_projects) -> None:
    # Same identifier on two projects (no platform passed): pick the newest build,
    # don't error.
    fake_projects([
        {"id": 1, "package_name": "com.dupe.app", "platform_display": "Android", "last_file_id": 5},
        {"id": 2, "package_name": "com.dupe.app", "platform_display": "Android", "last_file_id": 8},
    ])
    out = await resolve.resolve_latest_file("com.dupe.app")
    assert out["project_id"] == 2 and out["file_id"] == 8


async def test_platform_disambiguates_shared_identifier(fake_projects) -> None:
    # Android and iOS projects share the identifier; the API returns both.
    both = [
        {"id": 1, "package_name": "com.shared.app", "platform_display": "Android", "last_file_id": 5},
        {"id": 2, "package_name": "com.shared.app", "platform_display": "iOS", "last_file_id": 9},
    ]
    fake_projects(both)
    ios = await resolve.resolve_latest_file("com.shared.app", platform="ios")
    assert ios["project_id"] == 2 and ios["file_id"] == 9

    fake_projects(both)
    android = await resolve.resolve_latest_file("com.shared.app", platform="android")
    assert android["project_id"] == 1 and android["file_id"] == 5


async def test_platform_no_match_raises(fake_projects) -> None:
    fake_projects([{"id": 1, "platform_display": "Android", "last_file_id": 5}])
    with pytest.raises(AppknoxAPIError, match=r"\(ios\)"):
        await resolve.resolve_latest_file("com.only.android", platform="ios")


async def test_resolve_no_scanned_file_raises(fake_projects) -> None:
    fake_projects([{"id": 1, "package_name": "com.x", "last_file_id": None}])
    with pytest.raises(AppknoxAPIError, match="scanned file"):
        await resolve.resolve_latest_file("com.x")
