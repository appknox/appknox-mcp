"""Upload an app binary to the Appknox VAPT platform.

Flow: request a presigned URL, PUT the raw binary to it, then confirm to trigger
validation + scan. The confirm returns a submission id, so we poll the submission
until Appknox assigns a ``file_id`` (validation done); scanning then runs
asynchronously. All HTTP lives in the client — this module is just orchestration.
"""

import asyncio
from pathlib import Path
from typing import Any

from appknox_mcp.app import client, mcp
from appknox_mcp.client import AppknoxAPIError


async def _request_upload_url() -> dict[str, str]:
    """Request a presigned upload URL + signed key, validating the response."""
    handshake = await client.request_upload_url()
    if not (handshake.url and handshake.upload_key and handshake.upload_key_signed):
        raise AppknoxAPIError("Appknox did not return a usable upload URL")
    return {
        "url": handshake.url,
        "upload_key": handshake.upload_key,
        "upload_key_signed": handshake.upload_key_signed,
    }


async def _create_submission(upload_key: str, upload_key_signed: str) -> int:
    """Confirm the upload to create a submission; return its submission id."""
    submission = await client.create_submission(upload_key, upload_key_signed)
    if submission.submission_id is None:
        raise AppknoxAPIError("Appknox did not return a submission id")
    return submission.submission_id


async def _get_submission(submission_id: int) -> int | None:
    """Fetch a submission once: return its file_id if ready, None if still validating.

    Raises ``AppknoxAPIError`` if Appknox rejected the upload (``error_reason`` set).
    """
    submission = await client.get_submission(submission_id)
    if submission.error_reason:
        raise AppknoxAPIError(f"Appknox rejected the upload: {submission.error_reason}")
    return submission.file_id


async def _await_file_id(
    submission_id: int, timeout_seconds: int, interval: float = 3.0
) -> int:
    """Poll a submission until its file_id is available (validation done) or it fails."""
    waited = 0.0
    while True:
        file_id = await _get_submission(submission_id)
        if file_id is not None:
            return file_id
        if waited >= timeout_seconds:
            raise AppknoxAPIError(
                f"Timed out after {timeout_seconds}s waiting for Appknox to validate "
                f"the upload (submission {submission_id}). It may still succeed — "
                "check the Appknox dashboard."
            )
        await asyncio.sleep(interval)
        waited += interval


@mcp.tool
async def upload_binary(
    file_path: str, wait_for_file_id: bool = True, timeout_seconds: int = 300
) -> dict[str, Any]:
    """Upload an app binary (APK/IPA/etc.) to the Appknox VAPT platform and start a scan.

    Give the local path to a built binary. This runs the full upload flow — request
    a presigned URL, PUT the file, then trigger validation and the scan. When
    ``wait_for_file_id`` is true (default) it polls until Appknox has validated the
    build and assigned it a ``file_id`` (usually seconds), which is what later steps
    need. The scan and KnoxIQ analysis then run asynchronously — poll
    ``knoxiq_get_scan_status(file_id)`` or run ``knoxiq_verify_fixes`` to wait.
    Returns ``{file_id, submission_id, file_name}`` (``file_id`` omitted when
    ``wait_for_file_id`` is false). Raises ``AppknoxAPIError`` on any failure.
    """
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise AppknoxAPIError(f"No file found at '{file_path}'")
    handshake = await _request_upload_url()
    await client.put_to_storage(handshake["url"], path.read_bytes())
    submission_id = await _create_submission(
        handshake["upload_key"], handshake["upload_key_signed"]
    )
    result: dict[str, Any] = {"submission_id": submission_id, "file_name": path.name}
    if wait_for_file_id:
        result["file_id"] = await _await_file_id(submission_id, timeout_seconds)
    return result
