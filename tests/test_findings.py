"""Tests for the list_analyses/knoxiq_get_fix_plan tools in appknox_mcp.findings."""

from typing import Any

import pytest

from appknox_mcp import findings
from appknox_mcp.models import Analysis, File, KnoxIQFinding


def _analysis(
    analysis_id: int,
    computed_risk: int,
    exploitability_score: float | None = None,
    exploitability_likelihood: str | None = None,
) -> dict[str, Any]:
    return {
        "id": analysis_id,
        "vulnerability_id": 1000 + analysis_id,
        "vulnerability_name": f"Vuln {analysis_id}",
        "computed_risk": computed_risk,
        "computed_risk_display": {4: "Critical", 3: "High", 2: "Medium"}.get(computed_risk, "Low"),
        "cvss_base": "7.5",
        "vulnerability_scan_types": ["SAST"],
        "cwe": ["CWE-89"],
        "exploitability_score": exploitability_score,
        "exploitability_likelihood": exploitability_likelihood,
    }


class _FakeClient:
    """Stand-in for AppknoxClient with canned returns per named endpoint method."""

    def __init__(
        self,
        files: dict[int, dict[str, Any]] | None = None,
        analyses: dict[int, list[dict[str, Any]]] | None = None,
        knoxiq: dict[tuple[int, int], list[dict[str, Any]]] | None = None,
        project_files: dict[int, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._files = files or {}
        self._analyses = analyses or {}
        self._knoxiq = knoxiq or {}
        self._project_files = project_files or {}
        self.calls: list[tuple] = []

    async def get_file(self, file_id: int) -> File:
        self.calls.append(("get_file", file_id))
        return File.model_validate(self._files[file_id])

    async def list_analyses(self, file_id: int) -> list[Analysis]:
        self.calls.append(("list_analyses", file_id))
        return [Analysis.model_validate(a) for a in self._analyses.get(file_id, [])]

    async def list_knoxiq_findings(
        self, file_id: int, analysis_id: int
    ) -> list[KnoxIQFinding]:
        self.calls.append(("list_knoxiq_findings", file_id, analysis_id))
        return [
            KnoxIQFinding.model_validate(f)
            for f in self._knoxiq.get((file_id, analysis_id), [])
        ]

    async def list_project_files(self, project_id: int) -> list[File]:
        self.calls.append(("list_project_files", project_id))
        return [File.model_validate(f) for f in self._project_files.get(project_id, [])]


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch):
    def _install(**kwargs) -> _FakeClient:
        client = _FakeClient(**kwargs)
        monkeypatch.setattr(findings, "client", client)
        return client

    return _install


async def test_list_analyses_returns_all_rows(fake_client) -> None:
    fake_client(analyses={1: [_analysis(1, 4), _analysis(2, 3)]})

    rows = await findings.list_analyses(file_id=1, include_exploitability=False)

    assert [r["id"] for r in rows] == [1, 2]


async def test_get_file_info_returns_selected_fields(fake_client) -> None:
    fake_client(
        files={
            1: {
                "id": 1,
                "name": "MyApp",
                "package_name": "com.example.app",
                "version": "1.2.3",
                "platform": 0,
                "platform_display": "Android",
                "risk_count_critical": 2,
                "internal_secret": "must-not-leak",
            }
        }
    )

    info = await findings.get_file_info(file_id=1)

    assert info["package_name"] == "com.example.app"
    assert info["version"] == "1.2.3"
    assert info["platform_display"] == "Android"
    assert "internal_secret" not in info


async def test_min_risk_filters_without_calling_knoxiq_findings(fake_client) -> None:
    client = fake_client(analyses={1: [_analysis(1, 4), _analysis(2, 1)]})

    rows = await findings.list_analyses(file_id=1, min_risk=4, include_exploitability=False)

    assert [r["id"] for r in rows] == [1]
    assert not any(c[0] == "list_knoxiq_findings" for c in client.calls)


async def test_exploitability_comes_from_analyses_call_only(fake_client) -> None:
    client = fake_client(
        analyses={
            1: [
                _analysis(
                    1, 4, exploitability_score=8.5, exploitability_likelihood="High"
                ),
                _analysis(2, 1),
            ]
        },
    )

    rows = await findings.list_analyses(file_id=1, min_risk=4)

    assert len(rows) == 1
    assert rows[0]["exploitability_score"] == 8.5
    assert not any(c[0] == "list_knoxiq_findings" for c in client.calls)


async def test_min_exploitability_drops_low_scoring_analyses(fake_client) -> None:
    fake_client(
        analyses={
            1: [
                _analysis(1, 4, exploitability_score=9.0),
                _analysis(2, 4, exploitability_score=2.0),
            ]
        },
    )

    rows = await findings.list_analyses(file_id=1, min_exploitability=5.0)

    assert [r["id"] for r in rows] == [1]


async def test_list_analyses_sorts_by_exploitability_then_risk(fake_client) -> None:
    fake_client(
        analyses={
            1: [
                _analysis(1, computed_risk=4, exploitability_score=2.0),  # Critical, low exploit
                _analysis(2, computed_risk=2, exploitability_score=9.0),  # Medium, high exploit
                _analysis(3, computed_risk=3, exploitability_score=9.0),  # High, tied exploit
                _analysis(4, computed_risk=1, exploitability_score=None),  # Low, no score
            ]
        }
    )

    rows = await findings.list_analyses(file_id=1)

    # Exploitability score wins first (9.0 beats 2.0 beats missing/0.0); a tie
    # (id 2 vs 3) breaks on computed_risk (High beats Medium) — never on id order.
    assert [r["id"] for r in rows] == [3, 2, 1, 4]


async def test_include_exploitability_false_drops_fields(fake_client) -> None:
    fake_client(analyses={1: [_analysis(1, 4, exploitability_score=9.0)]})

    rows = await findings.list_analyses(file_id=1, include_exploitability=False)

    assert rows[0]["exploitability_score"] is None
    assert rows[0]["exploitability_likelihood"] is None


async def test_previous_file_id_returns_prior_build(fake_client) -> None:
    fake_client(
        files={9: {"id": 9, "project_id": 3}},
        project_files={3: [{"id": 9}, {"id": 7}, {"id": 4}]},
    )
    assert await findings.previous_file_id(9) == 7


async def test_previous_file_id_none_for_first_build(fake_client) -> None:
    fake_client(files={9: {"id": 9, "project_id": 3}}, project_files={3: [{"id": 9}]})
    assert await findings.previous_file_id(9) is None


async def test_knoxiq_get_fix_plan_fetches_only_requested_ids(fake_client) -> None:
    client = fake_client(
        knoxiq={(1, 1): [{"finding_id": "F-0", "developer_prompt": "fix it"}]}
    )

    plan = await findings.knoxiq_get_fix_plan(file_id=1, analysis_ids=[1])

    assert plan[0]["analysis_id"] == 1
    assert plan[0]["findings"][0]["finding_id"] == "F-0"
    assert plan[0]["findings"][0]["developer_prompt"] == "fix it"
    assert client.calls == [("list_knoxiq_findings", 1, 1)]


async def test_knoxiq_prepare_fix_returns_one_findings_set(fake_client) -> None:
    poc = {"poc_title": "t", "verification_steps": [{"step_number": 1, "command": "grep x"}]}
    fake_client(
        knoxiq={(9, 405): [{"finding_id": "F-0", "developer_prompt": "do it", "poc": poc}]}
    )

    result = await findings.knoxiq_prepare_fix(9, 405)

    assert result["file_id"] == 9
    assert result["analysis_id"] == 405
    assert result["findings"][0]["poc"] == poc
