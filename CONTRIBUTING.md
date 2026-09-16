# Contributing

## Setup

```bash
uv sync
uv run pre-commit install
```

The second command wires up git's `pre-commit` hook so black, ruff, and mypy
(plus a few hygiene checks) run automatically on every `git commit` — see
`.pre-commit-config.yaml`. It only touches files you've staged, so it's fast.

To run everything by hand (e.g. before opening a PR):

```bash
uv run pre-commit run --all-files
```

CI runs this same command on every PR — a local git hook is opt-in and
skippable with `git commit --no-verify`, so CI is what actually enforces it.

## Branch rules

`develop` is the default branch and requires at least one approving review
plus a green CI run before a PR can merge — direct pushes aren't allowed for
regular contributors. Target `develop` with your PR unless you're stacking on
another open PR. (Repo admins can still push directly — see Releasing below,
which relies on exactly that to bump the version with no PR round-trip.)

## Tests

```bash
uv run pytest -q
```

## Releasing

```bash
./scripts/release.sh patch      # or minor / major
```

Bumps `pyproject.toml`'s version, pushes it straight to `develop`, tags it,
and creates a GitHub Release using your own `gh` login — which is what
triggers `.github/workflows/publish.yml` to actually build, test, and publish
to PyPI. No PAT or stored secret involved: since it's your own account doing
the push and creating the release, branch protection's admin exemption and
GitHub's normal "a human did this" behavior both apply, exactly as if you'd
done each step by hand.

Must be run from a clean `develop` checkout, by an account with admin access
to this repo (needed to push directly, bypassing the PR requirement above).
