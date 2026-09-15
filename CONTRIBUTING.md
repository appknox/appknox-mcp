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
plus a green CI run before a PR can merge — direct pushes aren't allowed.
Target `develop` with your PR unless you're stacking on another open PR.

## Tests

```bash
uv run pytest -q
```
