"""Typed shapes for Appknox public API responses.

Parsed once in ``client.py``, right where each response enters the system — the
one boundary CLAUDE.md-style conventions say untrusted external data should be
validated at. Everywhere else gets typed attribute access instead of
``payload.get("field")`` chains. The API is external and still evolving (fields
get added), so every model tolerates unknown extra fields and treats anything
not required for a request to work as optional.
"""

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(extra="ignore")


class File(_Model):
    """A file (build) — from ``GET /files/{id}`` and ``GET /projects/{id}/files``.

    ``knoxiq_status`` is only present for KnoxIQ-enabled orgs.
    """

    id: int
    name: str | None = None
    package_name: str | None = None
    version: str | None = None
    version_code: str | None = None
    platform: int | None = None
    platform_display: str | None = None
    project_id: int | None = None
    sast_status: str | None = None
    dast_status: str | None = None
    static_scan_progress: int | None = None
    knoxiq_status: int | None = None
    risk_count_critical: int | None = None
    risk_count_high: int | None = None
    risk_count_medium: int | None = None
    risk_count_low: int | None = None
    risk_count_passed: int | None = None
    risk_count_untested: int | None = None
    is_last_file: bool | None = None


class Project(_Model):
    """A project — from ``GET /projects``."""

    id: int
    package_name: str | None = None
    platform: int | None = None
    platform_display: str | None = None
    last_file_id: int | None = None
    file_count: int | None = None


class Analysis(_Model):
    """A vulnerability analysis — from ``GET /files/{id}/analyses``.

    ``exploitability_score``/``exploitability_likelihood`` are only present for
    KnoxIQ-enabled orgs.
    """

    id: int
    vulnerability_id: int | None = None
    vulnerability_name: str | None = None
    computed_risk: int | None = None
    computed_risk_display: str | None = None
    cvss_base: str | None = None
    vulnerability_scan_types: list[Any] | None = None
    cwe: list[str] | None = None
    exploitability_score: float | None = None
    # Raw IntegerChoices code from the API (0 Unknown, 1 Passed, 2 Low,
    # 3 Medium, 4 High) — unlike computed_risk, there is no companion
    # `exploitability_likelihood_display` field; findings.py derives the
    # label itself. This was `str` until it was found to reject every real
    # response (the API never actually sends a string here).
    exploitability_likelihood: int | None = None


class KnoxIQFinding(_Model):
    """One KnoxIQ finding — from ``GET .../analyses/{id}/knoxiq_findings``."""

    finding_id: str
    title: str | None = None
    description: str | None = None
    validation: dict | None = None
    remediation: dict | None = None
    poc: dict | None = None
    developer_prompt: str | None = None
    exploitability: dict | None = None
    scan_type: int | None = None
    scan_id: int | None = None


class UploadHandshake(_Model):
    """A presigned upload slot — from ``GET /uploads``."""

    url: str | None = Field(
        default=None, validation_alias=AliasChoices("url", "upload_url")
    )
    upload_key: str | None = None
    upload_key_signed: str | None = None


class Submission(_Model):
    """A submission — from ``POST /uploads`` and ``GET /submission/{id}``."""

    submission_id: int | None = None
    file_id: int | None = None
    error_reason: str | None = None
