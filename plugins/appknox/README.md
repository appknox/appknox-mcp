# Appknox KnoxIQ plugin

Connects Claude Code to [Appknox](https://www.appknox.com) KnoxIQ so it can fetch
the vulnerabilities Appknox found in your mobile app, fix them in your repo,
verify each fix with the finding's own proof-of-concept, and confirm it with a
re-scan.

## Install

```
/plugin install appknox --marketplace appknox/appknox-mcp
```

## What it adds

- **MCP server `appknox`** — runs `uvx appknox-mcp==<pinned version>` locally
  (the [`appknox-mcp`](https://pypi.org/project/appknox-mcp/) package from PyPI).
- **Commands** — `/appknox:triage`, `/appknox:fix`, `/appknox:upload`,
  `/appknox:verify`.
- **Agent** — `appknox-fixer`, which fixes one finding and verifies it with its PoC.

## Configuration

On enable, Claude Code asks for:

| Option | Required | Description |
|---|---|---|
| Appknox access token | Yes | Service-account credential `<Access Key ID>:<Secret>`, stored in your OS credential store. See [Credentials](https://github.com/appknox/appknox-mcp#credentials). |
| Base URL | No | Defaults to `https://publicapi.appknox.com`; change only for a dedicated/on-prem instance. |

Requires [`uv`](https://docs.astral.sh/uv/) on your `PATH`.

## What it runs, sends, and fetches

- **Runs:** the `appknox-mcp` Python process on your machine, over stdio.
- **Sends:** HTTPS requests to your Appknox base URL only, authenticated with
  your access token. Requests carry build/vulnerability IDs and, for
  `upload_binary`, the app binary you choose (uploaded directly to Appknox
  storage through a presigned URL).
- **Fetches:** build metadata, vulnerability analyses, KnoxIQ findings
  (exploitability, PoC verification steps, remediation guidance).
- **Never sends:** your source code. Fixes and PoC checks run locally in Claude
  Code; the server only reads findings and uploads binaries you point it at.

## Privacy

Data handled by Appknox is covered by the
[Appknox Privacy Policy](https://www.appknox.com/privacy-policy). The plugin
itself stores nothing beyond the token Claude Code keeps in your OS credential
store.

## Support

Issues: <https://github.com/appknox/appknox-mcp/issues>
