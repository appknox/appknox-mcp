"""User-invoked workflow prompts and the remote-mode instruction split."""

import pytest

from appknox_mcp import findings, prompts, remote, remote_upload, upload
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


def test_prompts_use_split_upload_in_remote_mode():
    assert "upload_binary(path)" in prompts.verify()
    prompts.set_remote_mode(True)
    text = prompts.verify()
    assert "upload_binary" not in text
    assert "upload_start" in text and "upload_complete" in text


def test_remote_workflow_text_has_no_local_upload_tool():
    assert "upload_binary" not in workflow_text(remote=True)
    assert "upload_binary" in workflow_text(remote=False)


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


async def test_upload_start_output_is_data_only(monkeypatch):
    async def handshake():
        return {
            "url": "https://storage.test/o",
            "upload_key": "k",
            "upload_key_signed": "s",
        }

    monkeypatch.setattr(upload, "_request_upload_url", handshake)
    result = await remote_upload.upload_start()
    assert "next_step" not in result
    assert set(result) >= {
        "presigned_url",
        "upload_key",
        "upload_key_signed",
        "put_command",
    }


def test_upload_tools_flag(monkeypatch):
    monkeypatch.setenv("APPKNOX_API_BASE_URL", "https://api.appknox.test")
    monkeypatch.setenv("APPKNOX_MCP_PUBLIC_URL", "https://mcp.appknox.test")
    assert remote.RemoteConfig.from_env().upload_tools is True
    monkeypatch.setenv("APPKNOX_MCP_UPLOAD_TOOLS", "false")
    assert remote.RemoteConfig.from_env().upload_tools is False
    monkeypatch.setenv("APPKNOX_MCP_UPLOAD_TOOLS", "")
    assert remote.RemoteConfig.from_env().upload_tools is True
