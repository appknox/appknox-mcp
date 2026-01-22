# Appknox MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that wraps the [Appknox CLI](https://github.com/appknox/appknox-go) for mobile application security testing.

## Prerequisites

- **Node.js** 18 or higher
- **Appknox CLI** - See [installation instructions](https://github.com/appknox/appknox-go#installation)
- **Appknox Access Token** - Get from [Appknox Dashboard](https://secure.appknox.com) → Settings → Developer Settings

## Installation

```bash
npm install -g @appknox/mcp-server
```

## Configuration

### Authentication

Configure your access token using Appknox CLI:

```bash
appknox init
```

This will prompt for your access token and save it to `~/.config/appknox.json`.

Alternatively, set the `APPKNOX_ACCESS_TOKEN` environment variable if you prefer not to use the config file.

For additional configuration options (API host, region, proxy), see [Appknox CLI documentation](https://github.com/appknox/appknox-go#configuration).

### Claude Desktop Setup

Add to your Claude Desktop config:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "appknox": {
      "command": "npx",
      "args": ["-y", "@appknox/mcp-server"]
    }
  }
}
```

If you haven't run `appknox init`, you can set the token directly in the config:

```json
{
  "mcpServers": {
    "appknox": {
      "command": "npx",
      "args": ["-y", "@appknox/mcp-server"],
      "env": {
        "APPKNOX_ACCESS_TOKEN": "your-token-here"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APPKNOX_ACCESS_TOKEN` | Your Appknox API access token | Read from `~/.config/appknox.json` |
| `APPKNOX_CLI_PATH` | Absolute path to the Appknox CLI binary | `/usr/local/bin/appknox` |
| `LOG_LEVEL` | Logging level (`debug`, `info`, `warn`, `error`) | `info` |

If the Appknox CLI is installed in a non-standard location, set `APPKNOX_CLI_PATH`:

```json
{
  "mcpServers": {
    "appknox": {
      "command": "npx",
      "args": ["-y", "@appknox/mcp-server"],
      "env": {
        "APPKNOX_CLI_PATH": "/opt/homebrew/bin/appknox"
      }
    }
  }
}
```

Restart Claude Desktop after updating.

## Available Tools

The MCP server exposes Appknox CLI commands as tools:

| Tool | Description |
|------|-------------|
| `appknox_whoami` | Show current authenticated user information |
| `appknox_organizations` | List all organizations accessible to the user |
| `appknox_projects` | List projects with optional filtering by platform, package name, or search query |
| `appknox_files` | List all files (app versions) for a specific project. Requires `project_id` |
| `appknox_analyses` | List security analysis results (vulnerabilities) for a file. Requires `file_id` |
| `appknox_vulnerability` | Get detailed information about a specific vulnerability |
| `appknox_owasp` | Fetch OWASP category details by ID |
| `appknox_upload` | Upload an APK/IPA file for security scanning. Returns `file_id` |
| `appknox_cicheck` | Check vulnerabilities against a risk threshold (for CI/CD pipelines) |
| `appknox_sarif` | Generate a SARIF report for integration with code analysis tools |
| `appknox_reports_create` | Create a vulnerability report for a file |
| `appknox_reports_download` | Download vulnerability report as CSV. Returns content directly |
| `appknox_dastcheck` | Check DAST (dynamic scan) status and results |

### Tool Workflow

Most tools require IDs that come from other tools:

```
appknox_projects → project_id → appknox_files → file_id → appknox_analyses
                                                       → appknox_reports_download
                                                       → appknox_cicheck
                                                       → appknox_sarif
```

## Usage Examples

### Basic Queries

```
"Who am I logged in as?"
"List all my organizations"
"Show me all my projects"
"List projects with package name containing 'com.example'"
```

### Working with Projects and Files

```
"List all files for project ID 1234"
"Show me the latest scan results for project 'MyApp'"
"What vulnerabilities were found in file ID 56789?"
```

### Uploading and Scanning

```
"Upload /Users/me/Downloads/myapp.apk for security scanning"
"Upload the app at /Users/me/Desktop/app.ipa and tell me the file ID"
```

> **Important**: File paths must be absolute paths on your local machine (e.g., `/Users/username/Downloads/app.apk`). Drag-and-drop uploads or sandbox paths won't work.

### Security Analysis

```
"Show all critical and high vulnerabilities for file ID 12345"
"Check if file ID 12345 passes the security threshold for 'high' risk"
"Run a CI check on file 12345 with medium risk threshold"
```

### Reports and Documentation

```
"Download the vulnerability report for file ID 12345"
"Generate a SARIF report for file 12345 with high risk threshold"
"Get details about vulnerability ID 67890"
"What is OWASP M1_2016?"
```

### CI/CD Integration Scenarios

```
"Upload /path/to/app.apk and check if it has any critical vulnerabilities"
"Scan the app and fail if there are any high-risk issues"
"Generate a SARIF report I can upload to GitHub Security"
```

### Dynamic Analysis (DAST)

```
"Check the DAST scan status for file ID 12345"
"What are the dynamic scan results for file 12345 with medium risk threshold?"
```

## Troubleshooting

**Appknox CLI not found**: Verify installation with `which appknox`
**Authentication failed**: Check your token with `echo $APPKNOX_ACCESS_TOKEN`
**Debug logging**: Set `LOG_LEVEL=debug` in your environment

## Development

```bash
# Clone and build
git clone https://github.com/appknox/appknox-mcp.git
cd appknox-mcp
npm install
npm run build

# add to mcp config
 "appknox": {
    "command": "node",
    "args": ["/abosolute/path/to/appknox-mcp/build/index.js"]
  }
```

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for contribution guidelines.

## Resources

- [Appknox CLI](https://github.com/appknox/appknox-go)
- [MCP Specification](https://modelcontextprotocol.io)
- [Appknox Dashboard](https://secure.appknox.com)

## License

MIT
