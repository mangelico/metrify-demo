import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth import require_api_key
from src.config import settings
from src.database import get_db
from src.main import app
from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet


def _mock_wallet(balance=Decimal("100")):
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.balance_usdt = balance
    return w


def _mock_tx():
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.upstream_cost = Decimal("0.001")
    tx.fee_5pct = Decimal("0.00005")
    tx.total_cost = Decimal("0.00105")
    tx.status = TransactionStatus.completed
    return tx


_ANTHROPIC_RESULT = {
    "id": "msg_001",
    "model": "claude-haiku-4-5-20251001",
    "content": [{"type": "text", "text": "Hello!"}],
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "stop_reason": "end_turn",
}


def _make_mock_wrapper(estimate, result):
    w = AsyncMock()
    w.estimate_cost = AsyncMock(return_value=estimate)
    w.call = AsyncMock(return_value=result)
    return w


@pytest.mark.asyncio
async def test_rate_limit_returns_429_with_retry_after():
    """Second request with same key gets 429 + Retry-After when limit is 1/minute."""
    # Use a unique key per test run to avoid cross-test counter pollution
    unique_key = f"mk_live_{uuid.uuid4().hex}"
    wallet = _mock_wallet()
    tx = _mock_tx()

    async def db_override():
        db = AsyncMock()
        db.get = AsyncMock(return_value=wallet)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", tx.id) or None)
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_api_key] = lambda: wallet

    original_limit = settings.rate_limit_per_minute
    try:
        settings.rate_limit_per_minute = 1
        with patch(
            "src.routers.mcp._WRAPPERS",
            {"anthropic": _make_mock_wrapper(Decimal("0.001"), (_ANTHROPIC_RESULT, Decimal("0.0008")))},
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                r1 = await client.post(
                    "/mcp/call",
                    json={
                        "tool": "anthropic",
                        "params": {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    },
                    headers={"X-API-Key": unique_key},
                )
                r2 = await client.post(
                    "/mcp/call",
                    json={
                        "tool": "anthropic",
                        "params": {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                    },
                    headers={"X-API-Key": unique_key},
                )
    finally:
        settings.rate_limit_per_minute = original_limit
        app.dependency_overrides.clear()

    assert r1.status_code == 200
    assert r2.status_code == 429
    assert "Retry-After" in r2.headers


@pytest.mark.asyncio
async def test_rate_limit_different_keys_are_independent():
    """Two distinct API keys each get their own quota."""
    key_a = f"mk_live_{uuid.uuid4().hex}"
    key_b = f"mk_live_{uuid.uuid4().hex}"
    wallet = _mock_wallet()
    tx = _mock_tx()

    async def db_override():
        db = AsyncMock()
        db.get = AsyncMock(return_value=wallet)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", tx.id) or None)
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_api_key] = lambda: wallet

    original_limit = settings.rate_limit_per_minute
    payload = {
        "tool": "anthropic",
        "params": {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
    }
    try:
        settings.rate_limit_per_minute = 1
        with patch(
            "src.routers.mcp._WRAPPERS",
            {"anthropic": _make_mock_wrapper(Decimal("0.001"), (_ANTHROPIC_RESULT, Decimal("0.0008")))},
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                # key_a: first request ok, second blocked
                ra1 = await client.post("/mcp/call", json=payload, headers={"X-API-Key": key_a})
                ra2 = await client.post("/mcp/call", json=payload, headers={"X-API-Key": key_a})
                # key_b: fresh quota, first request should still be ok
                rb1 = await client.post("/mcp/call", json=payload, headers={"X-API-Key": key_b})
    finally:
        settings.rate_limit_per_minute = original_limit
        app.dependency_overrides.clear()

    assert ra1.status_code == 200
    assert ra2.status_code == 429
    assert rb1.status_code == 200
