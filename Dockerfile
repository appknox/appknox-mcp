# Container image for MCP catalogs that run servers in Docker (Docker MCP
# Catalog, Glama). Runs the same stdio server as `uvx appknox-mcp`.
#   docker build -t appknox-mcp .
#   docker run -i --rm -e APPKNOX_ACCESS_TOKEN=<id>:<secret> appknox-mcp
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md INSTALL.md LICENSE ./
COPY .claude-plugin ./.claude-plugin
COPY plugins ./plugins
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

RUN useradd --create-home --uid 10001 appknox
USER appknox

ENTRYPOINT ["/app/.venv/bin/appknox-mcp"]
