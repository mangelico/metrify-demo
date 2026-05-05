import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.database import get_db
from src.main import app
from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet
from src.auth import require_api_key
from src.wrappers.base import UpstreamError


def _mock_wallet(balance=Decimal("100")):
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.balance_usdt = balance
    return w


def _mock_tx(status=TransactionStatus.completed, cost=Decimal("0.001")):
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.upstream_cost = cost
    tx.fee_5pct = cost * Decimal("0.05")
    tx.total_cost = cost + tx.fee_5pct
    tx.status = status
    return tx


_ANTHROPIC_RESULT = {
    "id": "msg_001",
    "model": "claude-haiku-4-5-20251001",
    "content": [{"type": "text", "text": "Hello!"}],
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "stop_reason": "end_turn",
}


@pytest.mark.asyncio
async def test_mcp_call_happy_path():
    wallet = _mock_wallet()
    tx = _mock_tx()

    async def db_override():
        db = AsyncMock()
        # get_balance call after debit
        db.get = AsyncMock(return_value=wallet)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None  # no existing tx
        db.execute = AsyncMock(return_value=result_mock)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda obj: setattr(obj, "id", tx.id) or None)
        yield db

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        with patch(
            "src.routers.mcp._WRAPPERS",
            {
                "anthropic": _make_mock_wrapper(
                    estimate=Decimal("0.001"), result=(_ANTHROPIC_RESULT, Decimal("0.0008"))
                )
            },
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={
                        "tool": "anthropic",
                        "params": {
                            "messages": [{"role": "user", "content": "Hi"}],
                            "max_tokens": 10,
                        },
                    },
                )
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        assert "transaction_id" in data
        assert "X-Balance-Remaining" in resp.headers
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_call_unknown_tool():
    wallet = _mock_wallet()

    async def db_override():
        yield AsyncMock()

    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/mcp/call",
                json={"tool": "nonexistent", "params": {}},
            )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert detail["error"] == "tool_not_found"
        assert "available_tools" in detail
        assert "anthropic" in detail["available_tools"]
        assert "openai" in detail["available_tools"]
        assert "stability" in detail["available_tools"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_call_insufficient_balance():
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

    try:
        with patch(
            "src.routers.mcp._WRAPPERS",
            {"anthropic": _make_mock_wrapper(estimate=Decimal("10"), result=({}  , Decimal("10")))},
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "anthropic", "params": {"messages": [], "max_tokens": 10}},
                )
        assert resp.status_code == 402
        assert resp.json()["detail"]["error"] == "insufficient_balance"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_call_upstream_error_no_debit():
    wallet = _mock_wallet()
    tx = _mock_tx(status=TransactionStatus.upstream_error, cost=Decimal("0"))

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

    try:
        failing_wrapper = _make_mock_wrapper(estimate=Decimal("0.001"), result=({}  , Decimal("0")))
        failing_wrapper.call = AsyncMock(side_effect=UpstreamError("API down", 503))

        with patch("src.routers.mcp._WRAPPERS", {"anthropic": failing_wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "anthropic", "params": {"messages": [], "max_tokens": 10}},
                )
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert detail["error"] == "upstream_error"
        # wallet balance must be untouched (no debit on upstream error)
        assert wallet.balance_usdt == Decimal("100")
    finally:
        app.dependency_overrides.clear()


def _make_mock_wrapper(estimate: Decimal, result):
    w = AsyncMock()
    w.tool_name = "anthropic"
    w.estimate_cost = AsyncMock(return_value=estimate)
    w.call = AsyncMock(return_value=result)
    return w


_OPENAI_RESULT = {
    "id": "chatcmpl-001",
    "model": "gpt-4o-mini",
    "content": [{"type": "text", "text": "Hello!"}],
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "finish_reason": "stop",
}

_STABILITY_RESULT = {
    "model": "sdxl",
    "image_b64": "abc123==",
    "finish_reason": "SUCCESS",
}


@pytest.mark.asyncio
async def test_mcp_call_routes_to_openai():
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

    try:
        with patch(
            "src.routers.mcp._WRAPPERS",
            {"openai": _make_mock_wrapper(Decimal("0.001"), (_OPENAI_RESULT, Decimal("0.0005")))},
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={
                        "tool": "openai",
                        "params": {"messages": [{"role": "user", "content": "Hi"}], "max_tokens": 10},
                    },
                )
        assert resp.status_code == 200
        assert resp.json()["result"]["model"] == "gpt-4o-mini"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_call_routes_to_stability():
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

    try:
        with patch(
            "src.routers.mcp._WRAPPERS",
            {"stability": _make_mock_wrapper(Decimal("0.002"), (_STABILITY_RESULT, Decimal("0.002")))},
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp/call",
                    json={"tool": "stability", "params": {"prompt": "a cat", "model": "sdxl"}},
                )
        assert resp.status_code == 200
        assert resp.json()["result"]["model"] == "sdxl"
    finally:
        app.dependency_overrides.clear()
