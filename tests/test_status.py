"""Tests for knoxiq_get_scan_status (scan + KnoxIQ readiness with actionable messages)."""

from typing import Any

import pytest

from appknox_mcp import status
from appknox_mcp.models import File


class _FakeClient:
    """Serves get_file, whose payload carries knoxiq_status for KnoxIQ-enabled orgs."""

    def __init__(self, file_obj: dict[str, Any]) -> None:
        self.file_obj = file_obj

    async def get_file(self, file_id: int) -> File:
        return File.model_validate(self.file_obj)


def _file(
    sast: str = "Completed",
    dast: str = "Not Started",
    knoxiq_status: int | None = None,
) -> dict[str, Any]:
    return {
        "id": 1,
        "name": "App",
        "package_name": "com.x",
        "version": "1.0",
        "version_code": "1",
        "platform": 0,
        "platform_display": "Android",
        "project_id": 1,
        "sast_status": sast,
        "dast_status": dast,
        "knoxiq_status": knoxiq_status,
        "risk_count_critical": 0,
        "risk_count_high": 0,
        "risk_count_medium": 0,
        "risk_count_low": 0,
        "risk_count_passed": 0,
        "risk_count_untested": 0,
        "is_last_file": True,
    }


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch):
    def _install(file_obj: dict[str, Any]) -> _FakeClient:
        client = _FakeClient(file_obj)
        monkeypatch.setattr(status, "client", client)
        return client

    return _install


async def test_ready_when_knoxiq_completed(fake) -> None:
    fake(_file(knoxiq_status=4))
    out = await status.knoxiq_get_scan_status(1)
    assert out["ready"] is True
    assert out["knoxiq_status_code"] == 4
    assert out["knoxiq_status"] == "Completed"


async def test_not_ready_when_knoxiq_disabled(fake) -> None:
    fake(_file(knoxiq_status=0))
    out = await status.knoxiq_get_scan_status(1)
    assert out["ready"] is False
    assert "not enabled" in out["message"].lower()


async def test_not_ready_when_knoxiq_running(fake) -> None:
    fake(_file(knoxiq_status=3))
    out = await status.knoxiq_get_scan_status(1)
    assert out["ready"] is False
    assert "running" in out["message"].lower()


async def test_knoxiq_unavailable_but_scan_done_is_ready(fake) -> None:
    # knoxiq_status absent (not a KnoxIQ-enabled org): fall back to scan status.
    fake(_file(sast="Completed", knoxiq_status=None))
    out = await status.knoxiq_get_scan_status(1)
    assert out["ready"] is True
    assert out["knoxiq_status_code"] is None


async def test_knoxiq_unavailable_and_scan_pending_not_ready(fake) -> None:
    fake(_file(sast="Not Started", dast="Not Started", knoxiq_status=None))
    out = await status.knoxiq_get_scan_status(1)
    assert out["ready"] is False
    assert "not completed" in out["message"].lower()
