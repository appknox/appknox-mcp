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
        [
            {
                "id": 1,
                "package_name": "com.appknox.mfva",
                "platform": 0,
                "platform_display": "Android",
                "last_file_id": 5,
                "file_count": 3,
            }
        ]
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
    fake_projects(
        [
            {
                "id": 1,
                "package_name": "com.dupe.app",
                "platform": 0,
                "platform_display": "Android",
                "last_file_id": 5,
                "file_count": 5,
            },
            {
                "id": 2,
                "package_name": "com.dupe.app",
                "platform": 0,
                "platform_display": "Android",
                "last_file_id": 8,
                "file_count": 8,
            },
        ]
    )
    out = await resolve.resolve_latest_file("com.dupe.app")
    assert out["project_id"] == 2 and out["file_id"] == 8


async def test_platform_disambiguates_shared_identifier(fake_projects) -> None:
    # Android and iOS projects share the identifier; the API returns both.
    both = [
        {
            "id": 1,
            "package_name": "com.shared.app",
            "platform": 0,
            "platform_display": "Android",
            "last_file_id": 5,
            "file_count": 5,
        },
        {
            "id": 2,
            "package_name": "com.shared.app",
            "platform": 1,
            "platform_display": "iOS",
            "last_file_id": 9,
            "file_count": 9,
        },
    ]
    fake_projects(both)
    ios = await resolve.resolve_latest_file("com.shared.app", platform="ios")
    assert ios["project_id"] == 2 and ios["file_id"] == 9

    fake_projects(both)
    android = await resolve.resolve_latest_file("com.shared.app", platform="android")
    assert android["project_id"] == 1 and android["file_id"] == 5


async def test_platform_no_match_raises(fake_projects) -> None:
    fake_projects(
        [
            {
                "id": 1,
                "package_name": "com.only.android",
                "platform": 0,
                "platform_display": "Android",
                "last_file_id": 5,
                "file_count": 5,
            }
        ]
    )
    with pytest.raises(AppknoxAPIError, match=r"\(ios\)"):
        await resolve.resolve_latest_file("com.only.android", platform="ios")


async def test_resolve_no_scanned_file_raises(fake_projects) -> None:
    fake_projects(
        [
            {
                "id": 1,
                "package_name": "com.x",
                "platform": 0,
                "platform_display": "Android",
                "last_file_id": None,
                "file_count": 0,
            }
        ]
    )
    with pytest.raises(AppknoxAPIError, match="scanned file"):
        await resolve.resolve_latest_file("com.x")


def _project(pid: int, pkg: str, last_file_id: int, platform: str = "Android"):
    return {
        "id": pid,
        "package_name": pkg,
        "platform": 0 if platform == "Android" else 1,
        "platform_display": platform,
        "last_file_id": last_file_id,
        "file_count": 1,
    }


async def test_substring_matches_are_ignored(fake_projects) -> None:
    # The API filter is a substring match: a newer build of a *different* app
    # whose identifier contains ours must not win.
    fake_projects(
        [
            _project(1, "com.example.app", last_file_id=10),
            _project(2, "com.example.app.beta", last_file_id=99),
            _project(3, "com.example.application", last_file_id=98),
        ]
    )
    out = await resolve.resolve_latest_file("com.example.app", "android")
    assert out["project_id"] == 1
    assert out["file_id"] == 10


async def test_exact_match_is_case_insensitive_and_trimmed(fake_projects) -> None:
    fake_projects([_project(1, "com.Example.App", last_file_id=7, platform="iOS")])
    out = await resolve.resolve_latest_file("  com.example.app ", "ios")
    assert out["file_id"] == 7


async def test_only_near_matches_raises_with_suggestions(fake_projects) -> None:
    fake_projects(
        [
            _project(2, "com.example.app.beta", last_file_id=99),
            _project(3, "com.example.app.dev", last_file_id=98),
        ]
    )
    with pytest.raises(AppknoxAPIError) as err:
        await resolve.resolve_latest_file("com.example.app", "android")
    message = str(err.value)
    assert "No Appknox project found for package_name 'com.example.app'" in message
    assert "com.example.app.beta" in message and "com.example.app.dev" in message
