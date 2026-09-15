"""Typed shapes for Appknox public API responses.

Parsed once in ``client.py``, right where each response enters the system — the
one boundary CLAUDE.md-style conventions say untrusted external data should be
validated at. Everywhere else gets typed attribute access instead of
``payload.get("field")`` chains. The API is external and still evolving (fields
get added), so every model tolerates unknown extra fields and treats anything
not required for a request to work as optional.
"""

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class File(_Model):
    """A file (build) — from ``GET /files/{id}`` and ``GET /projects/{id}/files``.

    Field types are cross-checked against mycroft's ``PAFileSerializer`` /
    ``PAKnoxIQFileSerializer`` and the underlying Django model. Every field
    below is a plain (non-``required=False``, non-``allow_null``) serializer
    field sourced from a Django field or method that always returns a value —
    so all of them are required here, except ``knoxiq_status``, which is only
    present for KnoxIQ-enabled orgs (a whole extra serializer field, not just
    a nullable one).
    """

    id: int
    name: str
    package_name: str
    version: str
    version_code: str
    platform: int
    platform_display: str
    project_id: int
    sast_status: str
    dast_status: str
    knoxiq_status: int | None = None
    risk_count_critical: int
    risk_count_high: int
    risk_count_medium: int
    risk_count_low: int
    risk_count_passed: int
    risk_count_untested: int
    is_last_file: bool


class Project(_Model):
    """A project — from ``GET /projects``."""

    id: int
    package_name: str
    platform: int
    platform_display: str
    # None when the project has no uploaded builds yet (a real, common state
    # right after project creation) — PAProjectSerializer.get_last_file_id
    # explicitly returns None in that case.
    last_file_id: int | None = None
    file_count: int


class Analysis(_Model):
    """A vulnerability analysis — from ``GET /files/{id}/analyses``.

    ``exploitability_score``/``exploitability_likelihood``/``exploitability``
    are documented by mycroft as "or null" even for KnoxIQ-enabled orgs (no
    KnoxIQAnalysis row yet for this analysis) — genuinely optional, not just
    org-gated.
    """

    id: int
    vulnerability_id: int
    vulnerability_name: str
    computed_risk: int
    computed_risk_display: str
    cvss_base: str
    vulnerability_scan_types: list[Any] = Field(default_factory=list)
    cwe: list[str] = Field(default_factory=list)
    exploitability_score: float | None = None
    # Raw IntegerChoices code from the API (0 Unknown, 1 Passed, 2 Low,
    # 3 Medium, 4 High) — unlike computed_risk, there is no companion
    # `exploitability_likelihood_display` field; findings.py derives the
    # label itself. This was `str` until it was found to reject every real
    # response (the API never actually sends a string here).
    exploitability_likelihood: int | None = None


class KnoxIQFinding(_Model):
    """One KnoxIQ finding — from ``GET .../analyses/{id}/knoxiq_findings``.

    ``validation``/``remediation``/``poc``/``exploitability`` come from a
    stored JSON blob (``result_path_data``) and are declared ``required=False``
    with no default in mycroft's serializer — DRF drops the key entirely from
    the response when it's absent from that blob, so ``None`` here means
    "key wasn't present," same as everywhere else in this module.
    """

    finding_id: str
    title: str
    description: str
    validation: dict | None = None
    remediation: dict | None = None
    poc: dict | None = None
    developer_prompt: str | None = None
    exploitability: dict | None = None
    scan_type: int
    scan_id: int


class UploadHandshake(_Model):
    """A presigned upload slot — from ``GET /uploads``.

    All three fields are unconditionally constructed by mycroft's view
    (``PAUploadSet.list()``) on every successful response — never omitted or
    null.
    """

    url: str = Field(validation_alias=AliasChoices("url", "upload_url"))
    upload_key: str
    upload_key_signed: str


class Submission(_Model):
    """A submission — from ``POST /uploads`` and ``GET /submission/{id}``."""

    submission_id: int | None = None
    file_id: int | None = None
    error_reason: str | None = None

    @field_validator("file_id", mode="before")
    @classmethod
    def _pending_file_id_is_not_ready(cls, value: Any) -> Any:
        """While a submission is still validating (normal, on essentially
        every upload's first status check), the API returns the literal
        string "No file found" here instead of null — treat any non-numeric
        value as "not ready yet" rather than crash trying to parse it as an
        int. ``error_reason`` (checked separately by callers) carries the
        real reason for a submission that has actually, terminally failed.
        """
        if isinstance(value, str) and not value.isdigit():
            return None
        return value
