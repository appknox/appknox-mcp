# appknox-mcp — one image, two modes:
#
#   Local stdio (MCP catalogs: Docker MCP Toolkit, Glama):
#     docker run -i --rm -e APPKNOX_ACCESS_TOKEN=<id>:<secret> appknox-mcp
#
#   Remote, multi-user, OAuth (hosting mcp.appknox.com):
#     docker run --rm -p 8000:8000 --env-file deploy/remote.env \
#       appknox-mcp --http --host 0.0.0.0 --port 8000
#
# The image holds NO credentials. Remote mode needs none: every request brings
# its user's OAuth token, verified against Appknox. Configuration (public URL,
# API host) is supplied at run time — see deploy/remote.env.example.
FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app
# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
RUN uv sync --locked --no-dev --no-editable


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    FASTMCP_SHOW_SERVER_BANNER=false \
    FASTMCP_CHECK_FOR_UPDATES=off

RUN useradd --create-home --uid 10001 appknox
COPY --from=build --chown=appknox:appknox /app/.venv /app/.venv
USER appknox
WORKDIR /home/appknox

EXPOSE 8000
ENTRYPOINT ["appknox-mcp"]
