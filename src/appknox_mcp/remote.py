"""Remote (Streamable HTTP) mode: OAuth-authenticated, multi-user.

Local stdio mode is unchanged — one process per developer, a service-account
token from the environment, Appknox's Public API. Remote mode is one shared
server (e.g. https://mcp.appknox.com/mcp) where every request carries the
caller's own OAuth access token, issued by mycroft's OAuth server
(``/api/v2/oidc``, see mycroft/authcore/mcp_oauth.py):

* RFC 9728 protected-resource metadata points MCP clients at mycroft, which
  handles discovery, Dynamic Client Registration, login (password/SSO/MFA),
  consent and token issuance. This server never sees a password or a client
  secret.
* ``AppknoxTokenVerifier`` accepts a token only if mycroft does: it calls
  ``GET /api/me`` (an MCP-scoped view requiring ``mcp:read``) with it, and
  caches the verdict briefly.
* Tools keep calling the module-level ``client`` exactly as in stdio mode;
  ``RequestScopedClient`` resolves it per request to an
  ``InternalAppknoxClient`` acting as the calling user — never a shared
  credential — so mycroft's own project/org permissions apply to every call.

Token handling (v1): the user's token is forwarded to mycroft as-is. That is
token passthrough, which the MCP spec discourages; it is bounded here because
mycroft only accepts these tokens on the handful of views opted into MCP
scopes (mcp:read / mcp:upload), so a token issued for this server can do
nothing beyond what this server does. Replace with RFC 8693 token exchange if
mycroft grows one.
"""

import hashlib
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx
from fastmcp.server.auth import AccessToken, RemoteAuthProvider, TokenVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl

from appknox_mcp.client import _ensure_https

log = logging.getLogger("appknox_mcp.remote")

SCOPE_READ = "mcp:read"
SCOPE_UPLOAD = "mcp:upload"
# Path of mycroft's OAuth issuer under the API host.
ISSUER_PATH = "/api/v2/oidc"


@dataclass(frozen=True)
class RemoteConfig:
    """Everything remote mode needs, from flags/environment."""

    public_url: str  # where clients reach THIS server, e.g. https://mcp.appknox.com
    api_base_url: str  # mycroft host, e.g. https://api.appknox.com
    issuer_url: str  # mycroft OAuth issuer, e.g. https://api.appknox.com/api/v2/oidc
    host: str = "127.0.0.1"
    port: int = 8000
    path: str = "/mcp"
    # Stateless Streamable HTTP: no in-memory MCP session, so any replica can
    # serve any request (no sticky sessions). Every tool call here is
    # self-contained, so nothing is lost.
    stateless: bool = True
    # Off for clients that can neither read local files nor run a PUT (e.g.
    # Google Connected Apps): drops upload_binary.
    upload_tools: bool = True

    @property
    def public_host(self) -> str:
        """Host[:port] clients use; the only Host header the server accepts
        (DNS-rebinding protection), plus whatever APPKNOX_MCP_ALLOWED_HOSTS adds."""
        return urlparse(self.public_url).netloc

    @classmethod
    def from_env(
        cls,
        host: str | None = None,
        port: int | None = None,
        public_url: str | None = None,
    ) -> "RemoteConfig":
        api = os.environ.get("APPKNOX_API_BASE_URL", "").strip()
        if not api:
            raise SystemExit(
                "✗ Remote mode needs APPKNOX_API_BASE_URL (the Appknox API host, "
                "e.g. https://api.appknox.com)."
            )
        api = _ensure_https(api).rstrip("/")
        public = (public_url or os.environ.get("APPKNOX_MCP_PUBLIC_URL", "")).strip()
        if not public:
            raise SystemExit(
                "✗ Remote mode needs APPKNOX_MCP_PUBLIC_URL (this server's public "
                "base URL, e.g. https://mcp.appknox.com) or --public-url."
            )
        issuer = os.environ.get("APPKNOX_OAUTH_ISSUER", "").strip() or (
            api + ISSUER_PATH
        )
        return cls(
            public_url=public.rstrip("/"),
            api_base_url=api,
            issuer_url=issuer.rstrip("/"),
            host=host or os.environ.get("APPKNOX_MCP_HOST", "127.0.0.1"),
            port=port or int(os.environ.get("APPKNOX_MCP_PORT", "8000")),
            stateless=_env_flag("APPKNOX_MCP_STATELESS", True),
            upload_tools=_env_flag("APPKNOX_MCP_UPLOAD_TOOLS", True),
        )

    def allowed_hosts(self) -> list[str]:
        extra = os.environ.get("APPKNOX_MCP_ALLOWED_HOSTS", "")
        return [self.public_host, *(h.strip() for h in extra.split(",") if h.strip())]


def authorization_server_metadata_url(issuer_url: str) -> str:
    """RFC 8414 §3.1: the well-known path goes between the issuer's host and
    its path (``https://h/.well-known/oauth-authorization-server/api/v2/oidc``)."""
    parsed = urlparse(issuer_url)
    return (
        f"{parsed.scheme}://{parsed.netloc}"
        f"/.well-known/oauth-authorization-server{parsed.path.rstrip('/')}"
    )


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _token_key(token: str) -> str:
    # Never keep raw tokens as dict keys (they'd show up in heap dumps/debuggers
    # more readily); a digest is enough to look the cached verdict up.
    return hashlib.sha256(token.encode()).hexdigest()


class AppknoxTokenVerifier(TokenVerifier):
    """A token is valid iff mycroft accepts it on an MCP-scoped endpoint.

    ``GET /api/me`` requires the ``mcp:read`` scope for OAuth tokens and
    rejects expired/revoked tokens, superusers, and tokens from non-MCP apps,
    so one call checks everything this server needs — no introspection
    credential to provision or leak. Positive and negative verdicts are cached
    for ``cache_ttl`` seconds (revocation therefore takes effect within that
    window; mycroft still re-checks every proxied call itself).
    """

    def __init__(
        self,
        api_base_url: str,
        cache_ttl: float = 60.0,
        cache_size: int = 2048,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(required_scopes=[SCOPE_READ])
        self._http = httpx.AsyncClient(
            base_url=api_base_url, timeout=10.0, transport=transport
        )
        self._ttl = cache_ttl
        self._size = cache_size
        self._cache: OrderedDict[str, tuple[float, AccessToken | None]] = OrderedDict()

    @property
    def scopes_supported(self) -> list[str]:
        return [SCOPE_READ, SCOPE_UPLOAD]

    async def verify_token(self, token: str) -> AccessToken | None:
        key = _token_key(token)
        now = time.monotonic()
        cached = self._cache.get(key)
        if cached and cached[0] > now:
            self._cache.move_to_end(key)
            return cached[1]

        verdict = await self._ask_mycroft(token)
        self._cache[key] = (now + self._ttl, verdict)
        self._cache.move_to_end(key)
        while len(self._cache) > self._size:
            self._cache.popitem(last=False)
        return verdict

    async def _ask_mycroft(self, token: str) -> AccessToken | None:
        try:
            response = await self._http.get(
                "/api/me", headers={"Authorization": f"Bearer {token}"}
            )
        except httpx.RequestError as exc:
            # Fail closed, but say why in the server log.
            log.warning("Token check against Appknox failed: %s", exc)
            return None
        if response.status_code != 200:
            return None
        try:
            me: dict[str, Any] = response.json()
        except ValueError:
            return None
        return AccessToken(
            token=token,
            client_id=str(me.get("id", "")),
            # /api/me only answers tokens carrying mcp:read; whether the token
            # also has mcp:upload is enforced by mycroft on the upload views.
            scopes=[SCOPE_READ],
            expires_at=None,
            claims={
                "user_id": me.get("id"),
                "username": me.get("username"),
                "default_organization": me.get("default_organization"),
            },
        )


def build_auth(config: RemoteConfig, **verifier_kwargs: Any) -> RemoteAuthProvider:
    """RFC 9728 metadata (``/.well-known/oauth-protected-resource/mcp``)
    advertising mycroft as the one authorization server, plus the verifier."""
    return RemoteAuthProvider(
        token_verifier=AppknoxTokenVerifier(config.api_base_url, **verifier_kwargs),
        authorization_servers=[AnyHttpUrl(config.issuer_url)],
        base_url=config.public_url,
        scopes_supported=[SCOPE_READ, SCOPE_UPLOAD],
        resource_name="Appknox KnoxIQ",
        resource_documentation=AnyHttpUrl("https://github.com/appknox/appknox-mcp"),
    )


class RequestScopedClient:
    """Stands in for the module-level ``client`` the tools import.

    With an authenticated HTTP request in context it returns an
    ``InternalAppknoxClient`` acting as that request's user (one instance per
    token, LRU-bounded, so connection pools and the resolved org are reused
    across a session's calls). With no request token — stdio mode, or tests —
    it falls through to the static fallback client, so tool code is identical
    in both modes.
    """

    def __init__(self, fallback: Any, api_base_url: str | None, size: int = 512):
        self._fallback = fallback
        self._api_base_url = api_base_url
        self._size = size
        self._clients: OrderedDict[str, Any] = OrderedDict()

    def enable_remote(self, api_base_url: str) -> None:
        self._api_base_url = api_base_url

    def _current(self) -> Any:
        token = get_access_token()
        if token is None or self._api_base_url is None:
            if self._api_base_url is not None:
                # Remote mode must never fall back to a shared credential.
                raise PermissionError("No authenticated Appknox user for this request.")
            return self._fallback
        key = _token_key(token.token)
        client = self._clients.get(key)
        if client is None:
            from appknox_mcp.internal_client import InternalAppknoxClient

            client = InternalAppknoxClient(self._api_base_url, token.token)
            self._clients[key] = client
            while len(self._clients) > self._size:
                self._clients.popitem(last=False)
        else:
            self._clients.move_to_end(key)
        return client

    def __getattr__(self, name: str) -> Any:
        return getattr(self._current(), name)
