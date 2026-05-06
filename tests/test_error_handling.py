"""Tests for standardized error format and structured logging (TASK-19)."""
import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth import require_api_key
from src.database import get_db
from src.main import app
from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet
from src.wrappers.base import UpstreamError


def _mock_wallet(balance=Decimal("100")):
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.balance_usdt = balance
    return w


def _mock_tx(status=TransactionStatus.upstream_error, cost=Decimal("0")):
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.upstream_cost = cost
    tx.fee_5pct = Decimal("0")
    tx.total_cost = Decimal("0")
    tx.status = status
    return tx


@pytest.mark.asyncio
async def test_tool_not_found_returns_standard_error_format():
    wallet = _mock_wallet()

    async def db_override():
        yield AsyncMock()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/mcp/call", json={"tool": "nonexistent", "params": {}})

        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error"] == "TOOL_NOT_FOUND"
        assert "message" in detail
        assert "request_id" in detail
        assert detail["request_id"] != ""
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_insufficient_balance_returns_standard_error_format():
    wallet = _mock_wallet(balance=Decimal("0.000001"))

    async def db_override():
        db = AsyncMock()
        db.get = AsyncMock(return_value=wallet)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_api_key] = lambda: wallet

    mock_wrapper = AsyncMock()
    mock_wrapper.estimate_cost = AsyncMock(return_value=Decimal("10"))

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": mock_wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "anthropic", "params": {"messages": [], "max_tokens": 10}},
                )

        assert resp.status_code == 402
        detail = resp.json()["detail"]
        assert detail["error"] == "INSUFFICIENT_BALANCE"
        assert "message" in detail
        assert "request_id" in detail
        assert "required_usdt" in detail
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upstream_error_returns_standard_error_format():
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

    failing_wrapper = AsyncMock()
    failing_wrapper.estimate_cost = AsyncMock(return_value=Decimal("0.001"))
    failing_wrapper.call = AsyncMock(side_effect=UpstreamError("Service unavailable", 503))

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": failing_wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "anthropic", "params": {"messages": [], "max_tokens": 10}},
                )

        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert detail["error"] == "UPSTREAM_ERROR"
        assert "message" in detail
        assert "request_id" in detail
        assert "transaction_id" in detail
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_successful_call_includes_request_id():
    wallet = _mock_wallet()
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.upstream_cost = Decimal("0.001")
    tx.fee_5pct = Decimal("0.00005")
    tx.total_cost = Decimal("0.00105")

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

    mock_wrapper = AsyncMock()
    mock_wrapper.estimate_cost = AsyncMock(return_value=Decimal("0.001"))
    mock_wrapper.call = AsyncMock(return_value=({"result": "ok", "usage": {}}, Decimal("0.001")))

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": mock_wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "anthropic", "params": {"messages": [], "max_tokens": 10}},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "request_id" in data
        assert data["request_id"] != ""
    finally:
        app.dependency_overrides.clear()
