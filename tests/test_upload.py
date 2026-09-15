"""Tests for the upload_binary tool and its upload-flow helpers."""

from typing import Any

import pytest

from appknox_mcp import upload
from appknox_mcp.client import AppknoxAPIError
from appknox_mcp.models import Submission, UploadHandshake


class _FakeUploadClient:
    """Drives the upload flow via named client methods."""

    def __init__(self, submission_file_id: Any = 555) -> None:
        self.submission_file_id = submission_file_id
        self.calls: list[tuple] = []

    async def request_upload_url(self) -> UploadHandshake:
        self.calls.append(("request_upload_url",))
        return UploadHandshake.model_validate(
            {
                "upload_url": "https://storage/put",
                "upload_key": "k",
                "upload_key_signed": "k:sig",
            }
        )

    async def put_to_storage(self, url: str, content: bytes) -> None:
        self.calls.append(("put_to_storage", url))

    async def create_submission(
        self, upload_key: str, upload_key_signed: str
    ) -> Submission:
        self.calls.append(("create_submission", upload_key, upload_key_signed))
        return Submission.model_validate({"submission_id": 42})

    async def get_submission(self, submission_id: int) -> Submission:
        self.calls.append(("get_submission", submission_id))
        return Submission.model_validate(
            {"file_id": self.submission_file_id, "error_reason": None}
        )


async def test_upload_binary_happy_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    client = _FakeUploadClient()
    monkeypatch.setattr(upload, "client", client)
    binary = tmp_path / "app.apk"
    binary.write_bytes(b"PK\x03\x04")

    out = await upload.upload_binary(str(binary))

    assert out == {"submission_id": 42, "file_name": "app.apk", "file_id": 555}
    assert ("put_to_storage", "https://storage/put") in client.calls
    assert ("create_submission", "k", "k:sig") in client.calls


async def test_upload_binary_missing_file_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(upload, "client", _FakeUploadClient())
    with pytest.raises(AppknoxAPIError, match="No file found"):
        await upload.upload_binary("/does/not/exist.apk")


async def test_request_upload_url_blank_field_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """All three UploadHandshake fields are always present per mycroft's
    contract (enforced by the model itself), but an empty string would still
    pass pydantic's `str` validation — this is the remaining defensive check."""

    class _Blank:
        async def request_upload_url(self) -> UploadHandshake:
            return UploadHandshake.model_validate(
                {"upload_url": "", "upload_key": "k", "upload_key_signed": "k:sig"}
            )

    monkeypatch.setattr(upload, "client", _Blank())
    with pytest.raises(AppknoxAPIError, match="usable upload URL"):
        await upload._request_upload_url()


class _SubClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    async def get_submission(self, submission_id: int) -> Submission:
        return Submission.model_validate(self.payload)


def test_submission_coerces_no_file_found_string_to_none() -> None:
    """The real bug: while a submission is still validating (normal, on
    essentially every upload's first status check), the API returns the
    literal string "No file found" instead of null for file_id — this used
    to crash pydantic validation before the upload flow even got a chance to
    see it just meant "not ready yet"."""
    assert Submission.model_validate({"file_id": "No file found"}).file_id is None


def test_submission_accepts_numeric_file_id_string() -> None:
    """A genuinely numeric string should still parse as the int it represents."""
    assert Submission.model_validate({"file_id": "555"}).file_id == 555


async def test_get_submission_pending_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        upload, "client", _SubClient({"file_id": None, "error_reason": None})
    )
    assert await upload._get_submission(1) is None


async def test_get_submission_still_validating_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through the actual polling helper, using the real API's
    literal response shape while a submission is still validating."""
    monkeypatch.setattr(
        upload, "client", _SubClient({"file_id": "No file found", "error_reason": None})
    )
    assert await upload._get_submission(1) is None


async def test_get_submission_ready_returns_file_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        upload, "client", _SubClient({"file_id": 9, "error_reason": None})
    )
    assert await upload._get_submission(1) == 9


async def test_get_submission_error_reason_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        upload, "client", _SubClient({"file_id": None, "error_reason": "invalid apk"})
    )
    with pytest.raises(AppknoxAPIError, match="invalid apk"):
        await upload._get_submission(1)


async def test_await_file_id_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        upload, "client", _SubClient({"file_id": None, "error_reason": None})
    )

    async def _instant_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(upload.asyncio, "sleep", _instant_sleep)
    with pytest.raises(AppknoxAPIError, match="Timed out"):
        await upload._await_file_id(1, timeout_seconds=1, interval=1.0)
