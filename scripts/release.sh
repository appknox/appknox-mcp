#!/usr/bin/env bash
#
# Bump the version, tag it, and create a GitHub Release — run with YOUR OWN
# git/gh login, so this needs no stored secret or PAT at all: pushing the
# bump straight to develop is just you, an admin, pushing directly (exactly
# like any other commit you'd make), and creating the release with your own
# `gh` login is what triggers .github/workflows/publish.yml (which does the
# actual build/test/publish to TestPyPI or PyPI via Trusted Publishing — no
# version number to type there either, it reads pyproject.toml itself).
#
#   ./scripts/release.sh patch              # bump, tag, release to TestPyPI (default)
#   ./scripts/release.sh minor --real       # bump, tag, release to real PyPI
#   ./scripts/release.sh major
#
# Must be run from a clean, up-to-date `develop` checkout.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

info() { printf '  %s\n' "$1"; }
step() { printf '\n\033[1m▸ %s\033[0m\n' "$1"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$1" >&2; exit 1; }

BUMP="${1:-}"
case "$BUMP" in
  patch|minor|major) ;;
  *) die "Usage: $0 <patch|minor|major> [--real]  (default is a TestPyPI prerelease)" ;;
esac

PRERELEASE=true
if [ "${2:-}" = "--real" ]; then
  PRERELEASE=false
fi

cd "$REPO_DIR"

step "Checking the working tree"
[ -z "$(git status --porcelain)" ] || die "Working tree has uncommitted changes — commit or stash first."
BRANCH="$(git branch --show-current)"
[ "$BRANCH" = "develop" ] || die "On branch '$BRANCH' — checkout develop first: git checkout develop"

step "Syncing develop"
git pull --ff-only

step "Bumping the $BUMP version"
uv version --bump "$BUMP"
VERSION="$(uv version --short)"
TAG="v$VERSION"
info "New version: $VERSION (tag: $TAG)"

if git rev-parse "$TAG" >/dev/null 2>&1; then
  die "Tag $TAG already exists — this version was already released."
fi

step "Committing and pushing"
git add pyproject.toml
git commit -m "Bump version to $VERSION"
git push origin develop
git tag "$TAG"
git push origin "$TAG"

step "Creating the GitHub Release"
FLAGS=(--title "$TAG" --generate-notes)
if [ "$PRERELEASE" = true ]; then
  FLAGS+=(--prerelease)
fi
gh release create "$TAG" "${FLAGS[@]}"

step "Done"
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
info "$TAG released — publish.yml is now building + publishing $([ "$PRERELEASE" = true ] && echo "to TestPyPI" || echo "to real PyPI")."
info "Watch it: https://github.com/$REPO/actions/workflows/publish.yml"
