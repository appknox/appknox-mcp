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

Restart Claude Desktop after updating.

## Available Tools

The MCP server exposes all Appknox CLI commands as tools:

**Information**: `whoami`, `organizations`, `projects`, `files`, `analyses`, `vulnerability`, `owasp`
**Actions**: `upload`, `cicheck`, `sarif`, `reports_create`, `reports_download`, `schedule_dast`, `dastcheck`

Simply ask Claude to perform security testing tasks in natural language.

## Usage Examples

```
"Upload /path/to/app.apk and scan for high-risk vulnerabilities"
"List all my Android projects"
"Generate a SARIF report for file ID 12345"
"Get vulnerability details for vulnerability ID 67890"
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

# Run locally
npm start
```

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for contribution guidelines.

## Resources

- [Appknox CLI](https://github.com/appknox/appknox-go)
- [MCP Specification](https://modelcontextprotocol.io)
- [Appknox Dashboard](https://secure.appknox.com)

## License

MIT
