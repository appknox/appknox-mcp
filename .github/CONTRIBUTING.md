# Contributing to Appknox MCP Server

Thank you for your interest in contributing to the Appknox MCP Server! This document provides guidelines for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment.

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report:
- Check the [existing issues](https://github.com/appknox/appknox-mcp/issues) to avoid duplicates
- Collect information about the bug (OS, Node.js version, package version, error messages)

When creating a bug report, use the bug report template and include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Error messages and logs (with `LOG_LEVEL=debug`)
- Environment details

### Suggesting Features

Feature requests are welcome! Please:
- Use the feature request template
- Clearly describe the feature and its use case
- Explain why this feature would be useful to most users
- Indicate if this would be a breaking change

### Pull Requests

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/appknox-mcp.git
   cd appknox-mcp
   ```

2. **Install Dependencies**
   ```bash
   npm install
   ```

3. **Create a Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

4. **Make Your Changes**
   - Follow the existing code style
   - Write clear, concise commit messages
   - Add comments for complex logic
   - Update documentation as needed

5. **Test Your Changes**
   ```bash
   # Build the project
   npm run build

   # Test locally
   npm start

   # Verify package contents
   npm pack --dry-run
   ```

6. **Update Documentation**
   - Update README.md if needed
   - Update CHANGELOG.md with your changes
   - Add/update inline code documentation

7. **Commit Your Changes**
   Use [Conventional Commits](https://www.conventionalcommits.org/):
   ```bash
   git commit -m "feat: add new vulnerability export tool"
   git commit -m "fix: resolve authentication timeout issue"
   git commit -m "docs: update installation instructions"
   ```

8. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a pull request using the PR template.

## Development Guidelines

### Code Style

- Use TypeScript for all source files
- Follow existing code formatting
- Use meaningful variable and function names
- Add JSDoc comments for public APIs
- Keep functions focused and single-purpose

### Error Handling

- Use custom error classes from `src/errors.ts`
- Always sanitize error messages
- Log errors with appropriate context
- Never expose sensitive information in errors

### Logging

- Use the logger from `src/logger.ts`
- Choose appropriate log levels (DEBUG, INFO, WARN, ERROR)
- Include relevant context in log metadata
- Avoid logging sensitive information

### Security

- Never commit credentials or tokens
- Validate and sanitize all user inputs
- Use path validation for file operations
- Follow the existing security patterns

### Testing

- Build and test your changes locally
- Test with actual MCP clients when possible
- Verify no new warnings or errors
- Test error scenarios

## Project Structure

```
appknox-mcp/
├── src/
│   ├── index.ts       # MCP server entry point
│   ├── tools.ts       # Tool definitions
│   ├── executor.ts    # CLI command executor
│   ├── errors.ts      # Custom error classes
│   └── logger.ts      # Logging system
├── scripts/
│   └── verify-build.js # Build verification
├── .github/           # GitHub templates
└── docs/              # Documentation
```

## Version Management

We use [Semantic Versioning](https://semver.org/):
- **Patch** (1.0.x): Bug fixes, no breaking changes
- **Minor** (1.x.0): New features, backward compatible
- **Major** (x.0.0): Breaking changes

For version bumps, see [PUBLISHING.md](../PUBLISHING.md) and [VERSION_BUMP_CHEATSHEET.md](../VERSION_BUMP_CHEATSHEET.md).

## Review Process

1. All PRs require review before merging
2. CI checks must pass
3. Documentation must be updated
4. CHANGELOG.md must be updated
5. Code must follow project standards

## Questions?

- Open an issue for questions
- Check existing documentation
- Review the [README.md](../README.md) and [QUICK_START.md](../QUICK_START.md)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

Thank you for contributing! 🎉
