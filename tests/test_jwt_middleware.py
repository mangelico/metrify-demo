"""
Tests for JWT Bearer middleware, RFC 9728 metadata endpoint, and tool behavior.

Tokens are signed with a real RSA-2048 key pair generated at module load.
The validator fixture has its _public_key pre-populated — no JWKS HTTP call.

Covers:
  - RFC 9728: GET /.well-known/oauth-protected-resource → 200 + correct JSON
  - Middleware 401 cases all include WWW-Authenticate header
  - Middleware: no header → 401, wrong scheme → 401, expired → 401,
                invalid → 401, wrong audience → 401,
                valid JWT → ContextVar set + call_next
  - Option A: multi-audience token accepted
  - Tools: JWT resolves key, no-auth defensive guard
"""
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from auth.middleware import BearerMiddleware, _current_consumer_key, _METADATA_PATH
from auth.jwt_validator import JWTValidator

# ── RSA key pair generated once for the entire test module ────────────────────

_PRIVATE_KEY = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend(),
)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()
_ISSUER = "metrify-backend"


def _make_token(
    sub: str = "ck_from_jwt",
    exp_offset: int = 3600,
    aud="metrify",
) -> str:
    """Mint a test JWT signed with the module-level RSA private key."""
    payload = {
        "sub": sub,
        "aud": aud,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "iss": _ISSUER,
    }
    return pyjwt.encode(payload, _PRIVATE_KEY, algorithm="RS256")


@pytest.fixture
def validator():
    """JWTValidator with public key pre-injected — no JWKS HTTP call."""
    v = JWTValidator(backend_url="http://test-backend", issuer=_ISSUER)
    v._public_key = _PUBLIC_KEY
    return v


@pytest.fixture
def middleware(validator):
    """BearerMiddleware instance (uses env vars set in conftest)."""
    return BearerMiddleware(AsyncMock(), validator=validator)


@pytest.fixture
def anthropic_fn(mock_server, mock_m):
    from tools.anthropic_tool import register
    return register(mock_server, mock_m)


# ── RFC 9728: Protected Resource Metadata ─────────────────────────────────────


async def test_protected_resource_metadata_endpoint(middleware):
    """GET /.well-known/oauth-protected-resource → 200 + correct JSON, no auth."""
    request = MagicMock()
    request.url.path = _METADATA_PATH
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["resource"].endswith("/mcp")
    assert isinstance(body["authorization_servers"], list)
    assert len(body["authorization_servers"]) == 1
    assert body["bearer_methods_supported"] == ["header"]
    assert "resource_documentation" in body
    # Public endpoint — downstream app is NOT called
    call_next.assert_not_called()


async def test_metadata_endpoint_requires_no_auth(middleware):
    """Metadata endpoint is accessible even without Authorization header."""
    request = MagicMock()
    request.url.path = _METADATA_PATH
    # Deliberately omit Authorization header
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 200


# ── 401 cases all include WWW-Authenticate ────────────────────────────────────


async def test_no_bearer_returns_401(middleware):
    """No Authorization header → 401 with WWW-Authenticate."""
    request = MagicMock()
    request.headers = {}
    request.url.path = "/mcp"
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["error"] == "unauthorized"
    call_next.assert_not_called()


async def test_401_includes_www_authenticate_header(middleware):
    """All 401 responses include WWW-Authenticate with resource_metadata."""
    request = MagicMock()
    request.headers = {}
    request.url.path = "/mcp"
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert "resource_metadata" in response.headers["WWW-Authenticate"]
    assert _METADATA_PATH in response.headers["WWW-Authenticate"]


async def test_non_bearer_scheme_returns_401(middleware):
    """Authorization header with wrong scheme → 401."""
    request = MagicMock()
    request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
    request.url.path = "/mcp"
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert body["error"] == "unauthorized" if (body := json.loads(response.body)) else True
    call_next.assert_not_called()


async def test_expired_jwt_returns_401(middleware):
    """Expired JWT → 401 token_expired with WWW-Authenticate."""
    token = _make_token(exp_offset=-1)

    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.url.path = "/mcp"
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert json.loads(response.body)["error"] == "token_expired"
    assert "WWW-Authenticate" in response.headers
    call_next.assert_not_called()


async def test_invalid_jwt_returns_401(middleware):
    """Malformed JWT → 401 invalid_token with WWW-Authenticate."""
    request = MagicMock()
    request.headers = {"Authorization": "Bearer not.a.valid.token"}
    request.url.path = "/mcp"
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert json.loads(response.body)["error"] == "invalid_token"
    assert "WWW-Authenticate" in response.headers
    call_next.assert_not_called()


async def test_wrong_audience_jwt_returns_401(middleware):
    """JWT with a different audience → 401."""
    token = _make_token(aud="some-other-service")

    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.url.path = "/mcp"
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    assert json.loads(response.body)["error"] == "invalid_token"
    call_next.assert_not_called()


# ── Valid JWT passes through ───────────────────────────────────────────────────


async def test_valid_jwt_sets_context_var_and_passes_through(middleware):
    """Valid JWT → _current_consumer_key populated AND call_next invoked."""
    token = _make_token(sub="ck_valid_consumer")
    mock_response = MagicMock()

    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.url.path = "/mcp"

    captured_key = None

    async def capturing_call_next(req):
        nonlocal captured_key
        captured_key = _current_consumer_key.get()
        return mock_response

    response = await middleware.dispatch(request, capturing_call_next)

    assert response is mock_response
    assert captured_key == "ck_valid_consumer"


async def test_option_a_multi_audience_token_accepted(middleware):
    """Option A: token with aud=[metrify, metrify-mcp] is accepted."""
    token = _make_token(aud=["metrify", "metrify-mcp"])
    mock_response = MagicMock()

    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    request.url.path = "/mcp"

    captured_key = None

    async def capturing_call_next(req):
        nonlocal captured_key
        captured_key = _current_consumer_key.get()
        return mock_response

    response = await middleware.dispatch(request, capturing_call_next)

    assert response is mock_response
    assert captured_key == "ck_from_jwt"


# ── Tool auth guard (defensive) ───────────────────────────────────────────────


async def test_bearer_token_resolves_consumer_key(anthropic_fn, mock_m):
    """JWT → ContextVar → tool billing uses the JWT consumer key."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="JWT auth works")]

    ctx_token = _current_consumer_key.set("ck_from_jwt")
    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
            result = await anthropic_fn("Hello!")

        assert result == "JWT auth works"
        mock_m._billing.check_balance.assert_called_once_with(
            consumer_api_key="ck_from_jwt", required=0.000065
        )
        mock_m._billing.charge.assert_called_once_with(
            consumer_api_key="ck_from_jwt", tool_name="anthropic", cost=0.000065
        )
    finally:
        _current_consumer_key.reset(ctx_token)


async def test_no_auth_returns_error_string(anthropic_fn, mock_m):
    """ContextVar=None → tool returns error string, no billing, no crash.

    In production the middleware blocks unauthenticated requests before they
    reach the tool. This test covers the defensive guard inside the tool itself.
    """
    result = await anthropic_fn("Hello!")

    assert "Error:" in result
    assert "autenticación" in result
    mock_m._billing.check_balance.assert_not_called()
    mock_m._billing.charge.assert_not_called()
