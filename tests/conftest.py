"""Shared pytest fixtures for appknox_mcp tests."""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create an empty git repository in a temp directory and return its path."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path
