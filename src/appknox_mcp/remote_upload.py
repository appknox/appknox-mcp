"""``upload_binary`` for remote mode, where the server can't read the caller's disk.

Same tool name and ``file_path`` argument as the stdio tool, so every client,
prompt and the Claude plugin uses one upload tool in both modes. A remote
server can't open the path and the bytes can't travel through a tool call, so
the upload's three operations split around the one that needs the file:

1. First call (``file_path`` only): the server requests a presigned storage
   URL from Appknox and returns ``put_command`` — an HTTP PUT of that exact
   file to that URL — plus an opaque ``upload_id``.
2. The caller runs ``put_command`` on its own machine; the binary goes
   straight to Appknox storage, never through this server.
3. Second call (``file_path`` + ``upload_id``): the server confirms the
   upload, which creates the submission (validation + scan), and waits for
   the build's ``file_id``.

Registered by ``server._run_remote`` in place of the stdio tool.
"""

import base64
import binascii
import json
import shlex
from pathlib import PurePath
from typing import Any

from appknox_mcp import upload
from appknox_mcp.app import STARTS_SCAN, mcp
from appknox_mcp.client import AppknoxAPIError

# Presigned PUT URLs from Appknox storage are short-lived.
_URL_TTL_HINT_SECONDS = 900


def _encode_upload_id(upload_key: str, upload_key_signed: str) -> str:
    raw = json.dumps({"k": upload_key, "s": upload_key_signed}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_upload_id(upload_id: str) -> tuple[str, str]:
    """The keys inside are Appknox's own (``upload_key_signed`` is signed by
    Appknox and checked when the submission is created), so this is only a
    container — tampering with it just makes the confirmation fail."""
    try:
        padded = upload_id + "=" * (-len(upload_id) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return str(data["k"]), str(data["s"])
    except (binascii.Error, ValueError, KeyError, TypeError) as exc:
        raise AppknoxAPIError(
            "upload_id is not one this server issued; start the upload again "
            "without upload_id."
        ) from exc


def _put_commands(url: str, file_path: str) -> dict[str, str]:
    """HTTP PUT of ``file_path`` to ``url``, quoted so neither the path nor the
    URL can break out of the command."""
    ps_path = file_path.replace("'", "''")
    ps_url = url.replace("'", "''")
    return {
        "posix": (
            "curl --fail --silent --show-error -X PUT "
            f"-T {shlex.quote(file_path)} {shlex.quote(url)}"
        ),
        "windows_powershell": (
            "curl.exe --fail --silent --show-error -X PUT " f"-T '{ps_path}' '{ps_url}'"
        ),
    }


async def remote_upload_binary(
    file_path: str,
    upload_id: str | None = None,
    wait_for_file_id: bool = True,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Upload an app binary (APK, AAB or IPA) from the caller's machine and start a scan.

    Without ``upload_id``: returns ``status: "awaiting_upload"``, an
    ``upload_id`` and ``put_command`` (an HTTP PUT of ``file_path`` to a
    one-time presigned URL, for macOS/Linux and for Windows), since this server
    cannot read the caller's files. With ``upload_id``: confirms that upload,
    which starts validation and scanning, and with ``wait_for_file_id``
    (default true) waits up to ``timeout_seconds`` for the new build's
    ``file_id``. Returns ``status: "submitted"``, ``submission_id``,
    ``file_name`` and ``file_id`` (when waited for). Returns an error when the
    uploaded file can't be found or the URL has expired.
    """
    file_name = PurePath(file_path).name
    if not file_name:
        raise AppknoxAPIError(f"file_path '{file_path}' does not name a file.")

    if upload_id is None:
        handshake = await upload._request_upload_url()
        return {
            "status": "awaiting_upload",
            "file_name": file_name,
            "upload_id": _encode_upload_id(
                handshake["upload_key"], handshake["upload_key_signed"]
            ),
            "put_command": _put_commands(handshake["url"], file_path),
            "expires_in_seconds_hint": _URL_TTL_HINT_SECONDS,
        }

    upload_key, upload_key_signed = _decode_upload_id(upload_id)
    submission_id = await upload._create_submission(upload_key, upload_key_signed)
    result: dict[str, Any] = {
        "status": "submitted",
        "submission_id": submission_id,
        "file_name": file_name,
    }
    if wait_for_file_id:
        result["file_id"] = await upload._await_file_id(submission_id, timeout_seconds)
    return result


def register() -> None:
    """Expose ``remote_upload_binary`` as ``upload_binary`` (remote mode only;
    the caller removes the stdio tool of the same name first)."""
    mcp.tool(
        remote_upload_binary,
        name="upload_binary",
        title="Upload build and start scan",
        annotations=STARTS_SCAN,
    )
