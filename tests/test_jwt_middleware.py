"""
Tests for JWT Bearer middleware and dual-auth tool behavior.

Covers:
  - Middleware: expired JWT → 401, invalid JWT → 401, no header → passthrough
  - Tools: JWT sets consumer key, param fallback, JWT priority, no-auth error string
"""
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt

from auth.middleware import BearerMiddleware, _current_consumer_key
from auth.jwt_validator import JWTValidator

_SECRET = "test-secret-for-tests-only"
_ISSUER = "metrify-backend"


def _make_token(
    sub: str = "ck_from_jwt",
    exp_offset: int = 3600,
    aud: str = "metrify-demo",
    secret: str = _SECRET,
) -> str:
    """Mint a signed test JWT."""
    payload = {
        "sub": sub,
        "aud": aud,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
        "iss": _ISSUER,
    }
    return pyjwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def validator():
    return JWTValidator(secret=_SECRET, issuer=_ISSUER)


@pytest.fixture
def anthropic_fn(mock_server, mock_m):
    from tools.anthropic_tool import register
    return register(mock_server, mock_m)


# ── Middleware unit tests ──────────────────────────────────────────────────────


async def test_expired_jwt_returns_401(validator):
    """Expired JWT → 401 before the tool is invoked."""
    token = _make_token(exp_offset=-1)  # already expired

    middleware = BearerMiddleware(AsyncMock(), validator=validator)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["error"] == "token_expired"
    call_next.assert_not_called()


async def test_invalid_jwt_returns_401(validator):
    """Malformed / wrong-signature JWT → 401 before the tool is invoked."""
    middleware = BearerMiddleware(AsyncMock(), validator=validator)
    request = MagicMock()
    request.headers = {"Authorization": "Bearer not.a.valid.token"}
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["error"] == "invalid_token"
    call_next.assert_not_called()


async def test_no_bearer_passes_through(validator):
    """No Authorization header → middleware passes through to next handler."""
    mock_response = MagicMock()
    middleware = BearerMiddleware(AsyncMock(), validator=validator)
    request = MagicMock()
    request.headers = {}
    call_next = AsyncMock(return_value=mock_response)

    response = await middleware.dispatch(request, call_next)

    assert response is mock_response
    call_next.assert_called_once_with(request)


async def test_valid_jwt_sets_context_var_and_passes_through(validator):
    """Valid JWT → _current_consumer_key is populated AND call_next is called."""
    token = _make_token(sub="ck_valid_consumer")
    mock_response = MagicMock()
    middleware = BearerMiddleware(AsyncMock(), validator=validator)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}

    captured_key = None

    async def capturing_call_next(req):
        nonlocal captured_key
        captured_key = _current_consumer_key.get()
        return mock_response

    response = await middleware.dispatch(request, capturing_call_next)

    assert response is mock_response
    assert captured_key == "ck_valid_consumer"


# ── Tool dual-auth behavior ────────────────────────────────────────────────────


async def test_bearer_token_resolves_consumer_key(anthropic_fn, mock_m):
    """JWT present → tool works without explicit consumer_api_key parameter."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="JWT auth works")]

    ctx_token = _current_consumer_key.set("ck_from_jwt")
    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
            result = await anthropic_fn("Hello!")  # no consumer_api_key

        assert result == "JWT auth works"
        mock_m._billing.check_balance.assert_called_once_with(
            consumer_api_key="ck_from_jwt", required=0.000065
        )
        mock_m._billing.charge.assert_called_once_with(
            consumer_api_key="ck_from_jwt", tool_name="anthropic", cost=0.000065
        )
    finally:
        _current_consumer_key.reset(ctx_token)


async def test_explicit_param_used_without_jwt(anthropic_fn, mock_m):
    """No JWT → explicit consumer_api_key parameter works (backwards compat)."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Param auth works")]

    with patch("anthropic.AsyncAnthropic") as mock_cls:
        mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
        result = await anthropic_fn("Hello!", consumer_api_key="ck_from_param")

    assert result == "Param auth works"
    mock_m._billing.check_balance.assert_called_once_with(
        consumer_api_key="ck_from_param", required=0.000065
    )


async def test_jwt_takes_priority_over_param(anthropic_fn, mock_m):
    """JWT key overrides consumer_api_key parameter when both are present."""
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="JWT wins")]

    ctx_token = _current_consumer_key.set("ck_from_jwt")
    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value.messages.create = AsyncMock(return_value=mock_response)
            result = await anthropic_fn("Hello!", consumer_api_key="ck_from_param")

        assert result == "JWT wins"
        # Billing must use the JWT key, not the parameter
        mock_m._billing.check_balance.assert_called_once_with(
            consumer_api_key="ck_from_jwt", required=0.000065
        )
    finally:
        _current_consumer_key.reset(ctx_token)


async def test_no_auth_returns_error_message(anthropic_fn, mock_m):
    """No JWT + no consumer_api_key → friendly error string, no crash, no charge."""
    result = await anthropic_fn("Hello!")  # no consumer_api_key, ContextVar is None

    assert "Error:" in result
    assert "autenticación" in result
    mock_m._billing.check_balance.assert_not_called()
    mock_m._billing.charge.assert_not_called()


async def test_wrong_audience_jwt_returns_401(validator):
    """JWT with audience for a different service → 401."""
    token = _make_token(aud="some-other-service")
    middleware = BearerMiddleware(AsyncMock(), validator=validator)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}
    call_next = AsyncMock()

    response = await middleware.dispatch(request, call_next)

    assert response.status_code == 401
    body = json.loads(response.body)
    assert body["error"] == "invalid_token"
    call_next.assert_not_called()


async def test_option_a_multi_audience_token_accepted(validator):
    """Option A: token with aud=[metrify-mcp, metrify-demo] is accepted."""
    token = _make_token(aud=["metrify-mcp", "metrify-demo"])
    mock_response = MagicMock()
    middleware = BearerMiddleware(AsyncMock(), validator=validator)
    request = MagicMock()
    request.headers = {"Authorization": f"Bearer {token}"}

    captured_key = None

    async def capturing_call_next(req):
        nonlocal captured_key
        captured_key = _current_consumer_key.get()
        return mock_response

    response = await middleware.dispatch(request, capturing_call_next)

    assert response is mock_response
    assert captured_key == "ck_from_jwt"
