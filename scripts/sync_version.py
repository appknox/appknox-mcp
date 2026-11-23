"""Propagate pyproject.toml's version into every listing manifest.

The package version is the single source of truth (bumped by release.sh via
`uv version`). Marketplace manifests each repeat it — and the Claude plugin and
Gemini extension also *pin* the exact PyPI version they launch, because the
Claude directory blocks unpinned `uvx` launchers. Run after every bump:

    python scripts/sync_version.py          # rewrite manifests
    python scripts/sync_version.py --check  # exit 1 if any are stale (CI/tests)

Stdlib only, so release.sh can run it with any Python 3.11+.
"""

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "appknox-mcp"


def package_version() -> str:
    with open(ROOT / "pyproject.toml", "rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def _pin(version: str) -> list[str]:
    return [f"{PACKAGE}=={version}"]


def expected(version: str) -> dict[str, list[tuple[tuple[Any, ...], Any]]]:
    """Per file: (json path, expected value) pairs."""
    return {
        "plugins/appknox/.claude-plugin/plugin.json": [(("version",), version)],
        "plugins/appknox/.mcp.json": [
            (("mcpServers", "appknox", "args"), _pin(version))
        ],
        "server.json": [
            (("version",), version),
            (("packages", 0, "version"), version),
        ],
        "gemini-extension.json": [
            (("version",), version),
            (("mcpServers", "appknox", "args"), _pin(version)),
        ],
    }


def _get(doc: Any, path: tuple[Any, ...]) -> Any:
    for key in path:
        doc = doc[key]
    return doc


def _set(doc: Any, path: tuple[Any, ...], value: Any) -> None:
    for key in path[:-1]:
        doc = doc[key]
    doc[path[-1]] = value


def main(check: bool) -> int:
    version = package_version()
    stale: list[str] = []
    for rel, fields in expected(version).items():
        path = ROOT / rel
        doc = json.loads(path.read_text())
        for json_path, value in fields:
            if _get(doc, json_path) != value:
                stale.append(f"{rel}: {'.'.join(map(str, json_path))}")
                _set(doc, json_path, value)
        if not check:
            path.write_text(json.dumps(doc, indent=2) + "\n")
    if check and stale:
        print(f"✗ Manifests not at version {version}:", *stale, sep="\n  ")
        print("Run: python scripts/sync_version.py")
        return 1
    if not check:
        print(f"✓ Manifests synced to {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv[1:]))
