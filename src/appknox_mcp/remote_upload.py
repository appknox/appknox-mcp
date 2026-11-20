"""Upload tools for remote mode, where the server can't read the caller's disk.

``upload_binary`` (stdio mode) opens a local path itself. A remote server
can't, and the bytes can't travel through a tool call either, so the upload
splits around the one step that needs the file:

1. ``upload_start`` — the server gets a presigned storage URL from Appknox and
   hands the agent an exact command to PUT the file there itself.
2. The agent runs that command locally; the binary goes straight from the
   developer's machine to Appknox storage, never through this server.
3. ``upload_complete`` — the server confirms the upload, which creates the
   submission and starts validation + scan, and waits for the ``file_id``.

Registered only in remote mode (see ``server.main``), in place of
``upload_binary``.
"""

from typing import Any

from appknox_mcp import upload
from appknox_mcp.app import READ_ONLY, STARTS_SCAN, mcp

# Presigned PUT URLs from Appknox storage are short-lived.
_URL_TTL_HINT_SECONDS = 900

# upload_start only asks Appknox for a presigned URL — nothing changes until
# upload_complete, which creates the submission and starts a scan.
_UPLOAD_STEP = {**READ_ONLY, "idempotentHint": False}


def _put_commands(url: str) -> dict[str, str]:
    quoted = url.replace("'", "'\\''")
    return {
        "posix": f"curl --fail --silent --show-error -X PUT -T <path-to-binary> '{quoted}'",
        "windows_powershell": (
            f'curl.exe --fail --silent --show-error -X PUT -T <path-to-binary> "{url}"'
        ),
    }


@mcp.tool(title="Start build upload", annotations=_UPLOAD_STEP)
async def upload_start() -> dict[str, Any]:
    """Step 1 of 3 to upload an app binary (APK/IPA) to Appknox from a remote server.

    Returns a short-lived presigned storage URL plus ``upload_key`` and
    ``upload_key_signed``. Step 2 is to PUT the local binary to that URL with
    the returned ``put_command`` (replace ``<path-to-binary>``); step 3 is
    ``upload_complete`` with the two keys. The URL accepts only this one upload.
    """
    handshake = await upload._request_upload_url()
    return {
        "upload_key": handshake["upload_key"],
        "upload_key_signed": handshake["upload_key_signed"],
        "presigned_url": handshake["url"],
        "expires_in_seconds_hint": _URL_TTL_HINT_SECONDS,
        "put_command": _put_commands(handshake["url"]),
        "next_step": (
            "Run put_command for your OS from the repo, with <path-to-binary> "
            "replaced by the built APK/IPA path and the URL unchanged. It must "
            "exit 0. Then call upload_complete(upload_key, upload_key_signed). "
            "If the PUT fails or the URL has expired, call upload_start again."
        ),
    }


@mcp.tool(title="Finish upload and start scan", annotations=STARTS_SCAN)
async def upload_complete(
    upload_key: str,
    upload_key_signed: str,
    wait_for_file_id: bool = True,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Step 3 of 3: confirm an upload started with ``upload_start`` and start its scan.

    Call only after the PUT from step 2 exited successfully. Creates the
    submission (Appknox validates the binary, then scans it) and, when
    ``wait_for_file_id`` is true, waits until Appknox assigns the build a
    ``file_id``. If Appknox can't find the uploaded object, the error says so —
    re-run the PUT, or start over with ``upload_start``.
    """
    submission_id = await upload._create_submission(upload_key, upload_key_signed)
    result: dict[str, Any] = {"submission_id": submission_id}
    if wait_for_file_id:
        result["file_id"] = await upload._await_file_id(submission_id, timeout_seconds)
    return result
