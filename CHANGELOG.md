# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-14

### Added

#### Core Features
- **Complete MCP Server Implementation**: Production-ready Model Context Protocol server wrapping Appknox CLI
- **15+ Security Tools**: All Appknox CLI commands exposed as MCP tools
  - Read-only tools: `whoami`, `organizations`, `projects`, `files`, `analyses`, `vulnerability`, `owasp`
  - Action tools: `upload`, `cicheck`, `sarif`, `reports_create`, `reports_download`, `schedule_dast`, `dastcheck`
- **TypeScript Implementation**: Full type safety with TypeScript source and type definitions

#### Error Handling
- **Custom Error Classes**: Production-grade error handling with specific error types
  - `CLINotFoundError`: Appknox CLI not installed
  - `AuthenticationError`: Authentication failures
  - `ValidationError`: Input validation errors
  - `CommandTimeoutError`: Command execution timeouts
  - `CommandExecutionError`: General command failures
  - `FilePathError`: File path validation errors
- **Error Classification**: Automatic error type detection and proper error reporting
- **Error Sanitization**: Prevents sensitive information leakage in error messages

#### Logging System
- **Structured Logging**: Comprehensive logging with metadata and context
- **Configurable Log Levels**: DEBUG, INFO, WARN, ERROR levels
- **Timestamp Support**: All log entries include ISO timestamps
- **stderr Output**: Logs to stderr to avoid interfering with MCP protocol on stdout
- **Environment Control**: Set `LOG_LEVEL=debug` for detailed logging

#### Security & Validation
- **Path Traversal Protection**: Detects and blocks directory traversal attacks
- **Null Byte Injection Prevention**: Validates against command injection attempts
- **Path Length Validation**: Limits path lengths to 4096 characters
- **Numeric ID Validation**: Ensures IDs are positive integers within safe range
- **Credential Management**: Secure handling via environment variables or config file
- **Error Message Sanitization**: Removes tokens and sensitive file paths from errors
- **Process Isolation**: Each CLI command runs in isolated child process
- **Timeout Protection**: Configurable timeouts (default 2 minutes) for all commands

#### npm Package Features
- **npx Support**: Run directly with `npx @appknox/mcp-server`
- **Global Installation**: Install globally with `npm install -g @appknox/mcp-server`
- **Executable Binary**: Proper shebang for command-line execution
- **Type Definitions**: Includes TypeScript declaration files
- **Source Maps**: Debug-friendly with source maps included

#### Build & Development
- **Automated Build Verification**: `scripts/verify-build.js` validates build output
- **Pre-publish Checks**: Runs build verification before npm publish
- **Version Management**: Integrated with `npm version` command

#### Documentation
- **Comprehensive README**: Installation, configuration, usage, security best practices
- **Quick Start Guide**: 5-minute setup guide
- **Publishing Guide**: Complete guide for maintainers with `npm version` workflows
- **Version Bump Cheatsheet**: Quick reference for version management
- **Contributing Guide**: Contribution guidelines and development workflow
- **GitHub Templates**: Issue templates and PR template

### Security

- **Zero Credentials in Code**: All credentials from environment or config file
- **Input Validation**: All user inputs validated using Zod schemas
- **File Path Security**: Protection against traversal, injection, and length attacks
- **Error Sanitization**: Automatic removal of sensitive data from errors
- **Authentication Checks**: Validates access token before command execution
- **Shell Injection Prevention**: Uses `shell: false` for all spawned processes
- **Graceful Shutdown**: Handles SIGINT and SIGTERM for clean termination

### Documentation

- `README.md`: Main documentation with installation and usage
- `CHANGELOG.md`: This changelog
- `PUBLISHING.md`: npm publishing guide with version management
- `QUICK_START.md`: 5-minute getting started guide
- `VERSION_BUMP_CHEATSHEET.md`: Quick reference for version bumps
- `REFACTORING_SUMMARY.md`: Technical implementation details
- `GITHUB_SETUP.md`: GitHub repository setup guide
- `.github/CONTRIBUTING.md`: Contribution guidelines
- `.github/PULL_REQUEST_TEMPLATE.md`: PR template
- `.github/ISSUE_TEMPLATE/bug_report.md`: Bug report template
- `.github/ISSUE_TEMPLATE/feature_request.md`: Feature request template
- `LICENSE`: MIT License

### Requirements

- Node.js >= 18.0.0
- Appknox CLI installed and in PATH
- Appknox access token (via environment variable or config file)

### Package Information

- **Package Name**: `@appknox/mcp-server`
- **Package Size**: ~19.9 kB (compressed)
- **Unpacked Size**: ~96 kB
- **Files**: 24 files in package
- **Dependencies**: `@modelcontextprotocol/sdk`, `zod`

[1.0.0]: https://github.com/appknox/appknox-mcp/releases/tag/v1.0.0
