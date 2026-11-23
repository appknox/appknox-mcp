"""User-invoked workflow prompts and the remote-mode instruction split."""

import pytest

from appknox_mcp import findings, prompts, remote
from appknox_mcp.app import mcp
from appknox_mcp.client import AppknoxAPIError
from appknox_mcp.instructions import SERVER_SUMMARY, workflow_text


@pytest.fixture(autouse=True)
def local_mode():
    prompts.set_remote_mode(False)
    yield
    prompts.set_remote_mode(False)


async def test_workflow_prompts_are_registered():
    names = {p.name for p in await mcp.list_prompts()}
    assert {"triage", "fix", "verify"} <= names


def test_triage_prompt_scopes_task_and_carries_workflow():
    text = prompts.triage("com.example.app", "android")
    assert "com.example.app (android)" in text
    assert "steps 1-4" in text
    assert "1. RESOLVE THE BUILD" in text


def test_fix_and_verify_prompts():
    assert "analysis 12, 15" in prompts.fix("analysis 12, 15", file_id="99")
    assert "build 99" in prompts.fix("all", file_id="99")
    assert "re-scanned build 101" in prompts.verify(new_file_id="101")
    assert "step 7" in prompts.verify(binary_path="app.apk")


def test_prompts_describe_remote_upload_in_remote_mode():
    assert "put_command" not in prompts.verify()
    prompts.set_remote_mode(True)
    text = prompts.verify()
    assert "upload_binary(path, upload_id)" in text
    assert "put_command" in text


def test_remote_workflow_text_keeps_one_upload_tool():
    for remote_mode in (True, False):
        text = workflow_text(remote=remote_mode)
        assert "upload_binary" in text
        assert "upload_start" not in text


def test_server_summary_is_neutral():
    for phrase in ("never", "always", "do not", "must"):
        assert phrase not in SERVER_SUMMARY.lower()


async def test_fix_plan_caps_analysis_ids(monkeypatch):
    calls = []

    async def fake(file_id, analysis_id):
        calls.append(analysis_id)
        return []

    monkeypatch.setattr(findings.client, "list_knoxiq_findings", fake, raising=False)
    with pytest.raises(AppknoxAPIError, match="at most 10"):
        await findings.knoxiq_get_fix_plan(1, list(range(11)))
    assert calls == []
    # Duplicates don't count against the cap.
    result = await findings.knoxiq_get_fix_plan(1, [5] * 20 + [6])
    assert [r["analysis_id"] for r in result] == [5, 6]


def test_upload_tools_flag(monkeypatch):
    monkeypatch.setenv("APPKNOX_API_BASE_URL", "https://api.appknox.test")
    monkeypatch.setenv("APPKNOX_MCP_PUBLIC_URL", "https://mcp.appknox.test")
    assert remote.RemoteConfig.from_env().upload_tools is True
    monkeypatch.setenv("APPKNOX_MCP_UPLOAD_TOOLS", "false")
    assert remote.RemoteConfig.from_env().upload_tools is False
    monkeypatch.setenv("APPKNOX_MCP_UPLOAD_TOOLS", "")
    assert remote.RemoteConfig.from_env().upload_tools is True
