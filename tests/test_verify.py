"""Tests for knoxiq_verify_fixes (cross-build resolution check, matched by vulnerability_id)."""

from typing import Any

import pytest

from appknox_mcp import findings, status, verify


def _row(
    vid: int,
    name: str,
    risk: str = "High",
    exploitability_score: float | None = None,
    exploitability_likelihood: str | None = None,
) -> dict[str, Any]:
    return {
        "vulnerability_id": vid,
        "vulnerability_name": name,
        "computed_risk_display": risk,
        "exploitability_score": exploitability_score,
        "exploitability_likelihood": exploitability_likelihood,
    }


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    ready: dict[str, Any],
    by_file: dict[int, list],
    prev: int | None = None,
) -> None:
    """Stub the scan-status, findings, and previous-build calls verify makes."""

    async def fake_status(_file_id: int) -> dict[str, Any]:
        return ready

    async def fake_list(
        file_id: int, min_risk: int | None = None, include_exploitability: bool = True
    ) -> list:
        return by_file.get(file_id, [])

    async def fake_prev(_file_id: int) -> int | None:
        return prev

    monkeypatch.setattr(status, "knoxiq_get_scan_status", fake_status)
    monkeypatch.setattr(findings, "list_analyses", fake_list)
    monkeypatch.setattr(findings, "previous_file_id", fake_prev)


async def test_not_ready_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(monkeypatch, {"ready": False, "message": "still running"}, {})
    out = await verify.knoxiq_verify_fixes(2)
    assert out["ready"] is False
    assert out["message"] == "still running"


async def test_verify_by_vulnerability_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    # New build still has 1001 open; 1002 is gone.
    _patch(monkeypatch, {"ready": True}, {2: [_row(1001, "A")]})
    out = await verify.knoxiq_verify_fixes(2, vulnerability_ids=[1001, 1002])
    assert {r["vulnerability_id"] for r in out["resolved"]} == {1002}
    assert {r["vulnerability_id"] for r in out["still_open"]} == {1001}
    assert out["summary"] == {"checked": 2, "resolved": 1, "still_open": 1}


async def test_verify_by_old_file_diff(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        {"ready": True},
        {
            1: [_row(1001, "A"), _row(1002, "B")],  # old build open set
            2: [_row(1002, "B"), _row(1003, "C", "Low")],  # new build open set
        },
    )
    out = await verify.knoxiq_verify_fixes(2, old_file_id=1)
    assert {r["vulnerability_id"] for r in out["resolved"]} == {1001}
    assert {r["vulnerability_id"] for r in out["still_open"]} == {1002}
    assert {r["vulnerability_id"] for r in out["new_or_regressed"]} == {1003}


async def test_verify_auto_derives_previous_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No old_file_id / vulnerability_ids given: baseline defaults to the previous build (1).
    _patch(
        monkeypatch,
        {"ready": True},
        {
            1: [_row(1001, "A"), _row(1002, "B")],  # previous build open set
            2: [_row(1002, "B")],  # new build open set
        },
        prev=1,
    )
    out = await verify.knoxiq_verify_fixes(2)
    assert out["old_file_id"] == 1
    assert {r["vulnerability_id"] for r in out["resolved"]} == {1001}
    assert {r["vulnerability_id"] for r in out["still_open"]} == {1002}


async def test_verify_first_build_has_no_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, {"ready": True}, {2: []}, prev=None)
    out = await verify.knoxiq_verify_fixes(2)
    assert out["old_file_id"] is None
    assert "first build" in out["message"]


async def test_verify_baseline_with_no_open_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch(monkeypatch, {"ready": True}, {5: [], 2: []}, prev=5)
    out = await verify.knoxiq_verify_fixes(2)
    assert out["summary"]["checked"] == 0
    assert "Nothing to compare" in out["message"]


async def test_still_open_carries_exploitability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 1001 stays open in the new build, but its exploitability dropped after the fix.
    _patch(
        monkeypatch,
        {"ready": True},
        {
            2: [
                _row(
                    1001, "A", exploitability_score=2.0, exploitability_likelihood="Low"
                )
            ]
        },
    )
    out = await verify.knoxiq_verify_fixes(2, vulnerability_ids=[1001])
    [entry] = out["still_open"]
    assert entry["exploitability_score"] == 2.0
    assert entry["exploitability_likelihood"] == "Low"
