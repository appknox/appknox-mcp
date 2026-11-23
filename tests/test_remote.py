"""Remote (Streamable HTTP + OAuth) mode: token verification, RFC 9728
metadata / 401 challenge, request-scoped client, and the split upload tools."""

import json
import sys
from types import SimpleNamespace

import httpx
import pytest
from starlette.testclient import TestClient

from appknox_mcp import remote, remote_upload, upload
from appknox_mcp.client import AppknoxAPIError

API = "https://api.appknox.test"
PUBLIC = "https://mcp.appknox.test"
CONFIG = remote.RemoteConfig(
    public_url=PUBLIC, api_base_url=API, issuer_url=f"{API}/api/v2/oidc"
)


def _me_transport(calls: list, status: int = 200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.path == "/api/me"
        if status != 200:
            return httpx.Response(status, json={"detail": "nope"})
        return httpx.Response(
            200, json={"id": 7, "username": "dev1", "default_organization": 3}
        )

    return httpx.MockTransport(handler)


# --- AppknoxTokenVerifier -----------------------------------------------------


async def test_verifier_accepts_token_mycroft_accepts():
    calls: list = []
    verifier = remote.AppknoxTokenVerifier(API, transport=_me_transport(calls))
    token = await verifier.verify_token("good")
    assert token is not None
    assert token.claims["user_id"] == 7
    assert token.claims["default_organization"] == 3
    assert "mcp:read" in token.scopes
    assert calls[0].headers["authorization"] == "Bearer good"


@pytest.mark.parametrize("status", [401, 403, 500])
async def test_verifier_rejects_token_mycroft_rejects(status):
    verifier = remote.AppknoxTokenVerifier(API, transport=_me_transport([], status))
    assert await verifier.verify_token("bad") is None


async def test_verifier_fails_closed_on_network_error():
    def boom(request):
        raise httpx.ConnectError("down")

    verifier = remote.AppknoxTokenVerifier(API, transport=httpx.MockTransport(boom))
    assert await verifier.verify_token("any") is None


async def test_verifier_caches_verdicts():
    calls: list = []
    verifier = remote.AppknoxTokenVerifier(API, transport=_me_transport(calls))
    await verifier.verify_token("t1")
    await verifier.verify_token("t1")
    assert len(calls) == 1
    await verifier.verify_token("t2")
    assert len(calls) == 2


async def test_verifier_cache_expires(monkeypatch):
    calls: list = []
    verifier = remote.AppknoxTokenVerifier(
        API, cache_ttl=10, transport=_me_transport(calls)
    )
    clock = [1000.0]
    monkeypatch.setattr(remote.time, "monotonic", lambda: clock[0])
    await verifier.verify_token("t1")
    clock[0] += 11
    await verifier.verify_token("t1")
    assert len(calls) == 2


async def test_verifier_cache_is_bounded():
    verifier = remote.AppknoxTokenVerifier(
        API, cache_size=2, transport=_me_transport([])
    )
    for tok in ("a", "b", "c"):
        await verifier.verify_token(tok)
    assert len(verifier._cache) == 2


# --- HTTP app: RFC 9728 metadata and the 401 challenge -----------------------


def _http_app():
    from fastmcp import FastMCP

    server = FastMCP(name="t", auth=remote.build_auth(CONFIG))
    return server.http_app(path="/mcp")


def test_protected_resource_metadata_points_at_mycroft():
    with TestClient(_http_app()) as http:
        resp = http.get("/.well-known/oauth-protected-resource/mcp")
    assert resp.status_code == 200
    meta = resp.json()
    assert meta["resource"].rstrip("/") == f"{PUBLIC}/mcp"
    assert [s.rstrip("/") for s in meta["authorization_servers"]] == [
        f"{API}/api/v2/oidc"
    ]
    assert set(meta["scopes_supported"]) == {"mcp:read", "mcp:upload"}


def test_unauthenticated_mcp_request_gets_rfc9728_challenge():
    with TestClient(_http_app()) as http:
        resp = http.post(
            "/mcp",
            content=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
            headers={
                "content-type": "application/json",
                "accept": "application/json, text/event-stream",
            },
        )
    assert resp.status_code == 401
    challenge = resp.headers["www-authenticate"]
    assert "resource_metadata=" in challenge
    assert "/.well-known/oauth-protected-resource" in challenge


# --- RequestScopedClient -----------------------------------------------------


def test_stdio_mode_uses_fallback(monkeypatch):
    fallback = SimpleNamespace(get_file="static")
    scoped = remote.RequestScopedClient(fallback, api_base_url=None)
    monkeypatch.setattr(remote, "get_access_token", lambda: None)
    assert scoped.get_file == "static"


def test_remote_mode_never_falls_back_to_shared_credential(monkeypatch):
    scoped = remote.RequestScopedClient(SimpleNamespace(get_file="static"), API)
    monkeypatch.setattr(remote, "get_access_token", lambda: None)
    with pytest.raises(PermissionError):
        _ = scoped.get_file


def test_remote_mode_builds_one_client_per_user(monkeypatch):
    built: list = []

    class FakeInternal:
        def __init__(self, base_url, token):
            built.append((base_url, token))
            self.token = token

    monkeypatch.setitem(
        sys.modules,
        "appknox_mcp.internal_client",
        SimpleNamespace(InternalAppknoxClient=FakeInternal),
    )
    scoped = remote.RequestScopedClient(SimpleNamespace(), API)
    current = {"token": "alice"}
    monkeypatch.setattr(
        remote, "get_access_token", lambda: SimpleNamespace(token=current["token"])
    )
    assert scoped.token == "alice"
    assert scoped.token == "alice"
    current["token"] = "bob"
    assert scoped.token == "bob"
    assert built == [(API, "alice"), (API, "bob")]


# --- RemoteConfig ------------------------------------------------------------


def test_config_requires_api_and_public_urls(monkeypatch):
    monkeypatch.delenv("APPKNOX_API_BASE_URL", raising=False)
    monkeypatch.delenv("APPKNOX_MCP_PUBLIC_URL", raising=False)
    with pytest.raises(SystemExit):
        remote.RemoteConfig.from_env()
    monkeypatch.setenv("APPKNOX_API_BASE_URL", "api.appknox.test")
    with pytest.raises(SystemExit):
        remote.RemoteConfig.from_env()
    config = remote.RemoteConfig.from_env(public_url=PUBLIC + "/")
    assert config.api_base_url == API
    assert config.issuer_url == f"{API}/api/v2/oidc"
    assert config.public_url == PUBLIC


# --- Remote upload_binary ------------------------------------------------------


async def test_remote_upload_first_call_returns_quoted_put_command(monkeypatch):
    async def handshake():
        return {
            "url": "https://storage.test/obj?sig=a'b",
            "upload_key": "k",
            "upload_key_signed": "ks",
        }

    monkeypatch.setattr(upload, "_request_upload_url", handshake)
    result = await remote_upload.remote_upload_binary("build/My App's.apk")
    assert result["status"] == "awaiting_upload"
    assert result["file_name"] == "My App's.apk"
    assert remote_upload._decode_upload_id(result["upload_id"]) == ("k", "ks")
    posix = result["put_command"]["posix"]
    assert posix.startswith("curl --fail")
    # Path and URL stay single shell words, whatever they contain.
    import shlex as _shlex

    words = _shlex.split(posix)
    assert words[words.index("-T") + 1] == "build/My App's.apk"
    assert words[-1] == "https://storage.test/obj?sig=a'b"
    ps = result["put_command"]["windows_powershell"]
    assert "-T 'build/My App''s.apk'" in ps


async def test_remote_upload_second_call_confirms_and_waits(monkeypatch):
    async def create(k, ks):
        assert (k, ks) == ("k", "ks")
        return 55

    async def wait(submission_id, timeout):
        assert submission_id == 55
        return 901

    monkeypatch.setattr(upload, "_create_submission", create)
    monkeypatch.setattr(upload, "_await_file_id", wait)
    upload_id = remote_upload._encode_upload_id("k", "ks")
    assert await remote_upload.remote_upload_binary("app.apk", upload_id) == {
        "status": "submitted",
        "submission_id": 55,
        "file_name": "app.apk",
        "file_id": 901,
    }
    result = await remote_upload.remote_upload_binary(
        "app.apk", upload_id, wait_for_file_id=False
    )
    assert "file_id" not in result


async def test_remote_upload_rejects_foreign_upload_id():
    with pytest.raises(AppknoxAPIError, match="not one this server issued"):
        await remote_upload.remote_upload_binary("app.apk", "not-base64-json!!")


def test_authorization_server_metadata_url_inserts_well_known():
    assert (
        remote.authorization_server_metadata_url("https://h.example/api/v2/oidc")
        == "https://h.example/.well-known/oauth-authorization-server/api/v2/oidc"
    )


def test_config_host_allowlist_and_stateless_default(monkeypatch):
    monkeypatch.setenv("APPKNOX_API_BASE_URL", API)
    monkeypatch.setenv("APPKNOX_MCP_PUBLIC_URL", "https://mcp.appknox.test")
    monkeypatch.setenv("APPKNOX_MCP_ALLOWED_HOSTS", "internal-lb:8000, ")
    config = remote.RemoteConfig.from_env()
    assert config.stateless is True
    assert config.allowed_hosts() == ["mcp.appknox.test", "internal-lb:8000"]
    monkeypatch.setenv("APPKNOX_MCP_STATELESS", "false")
    assert remote.RemoteConfig.from_env().stateless is False


def test_issuer_override_for_split_internal_and_public_hosts(monkeypatch):
    monkeypatch.setenv("APPKNOX_API_BASE_URL", "http://host.docker.internal:8010")
    monkeypatch.setenv("APPKNOX_MCP_PUBLIC_URL", "http://127.0.0.1:8020")
    monkeypatch.setenv("APPKNOX_OAUTH_ISSUER", "http://127.0.0.1:8010/api/v2/oidc")
    config = remote.RemoteConfig.from_env()
    assert config.api_base_url == "http://host.docker.internal:8010"
    assert config.issuer_url == "http://127.0.0.1:8010/api/v2/oidc"
