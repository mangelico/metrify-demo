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


def _mock_tx(cost=Decimal("0.001")):
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.upstream_cost = cost
    tx.fee_5pct = cost * Decimal("0.05")
    tx.total_cost = cost + tx.fee_5pct
    tx.status = TransactionStatus.completed
    return tx


def _mock_wrapper(estimate=Decimal("0.001"), result=None):
    if result is None:
        result = ({"output": "ok"}, Decimal("0.001"))
    w = AsyncMock()
    w.tool_name = "anthropic"
    w.estimate_cost = AsyncMock(return_value=estimate)
    w.call = AsyncMock(return_value=result)
    return w


def _db_override(wallet, tx=None):
    async def _override():
        db = AsyncMock()
        db.get = AsyncMock(return_value=wallet)
        existing = MagicMock()
        existing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=existing)
        db.add = MagicMock()
        db.commit = AsyncMock()
        if tx:
            db.refresh = AsyncMock(
                side_effect=lambda obj: setattr(obj, "id", tx.id) or None
            )
        else:
            db.refresh = AsyncMock()
        yield db

    return _override


# ---------------------------------------------------------------------------
# Test 1 — initialize handshake
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_initialize():
    wallet = _mock_wallet()
    app.dependency_overrides[get_db] = _db_override(wallet)
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"},
                    },
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["jsonrpc"] == "2.0"
        assert body["id"] == 1
        result = body["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "modelo-gateway"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 2 — tools/list returns all 6 tools with required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_tools_list_format():
    wallet = _mock_wallet()
    app.dependency_overrides[get_db] = _db_override(wallet)
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 2
        tools = body["result"]["tools"]
        names = {t["name"] for t in tools}
        assert names == {"anthropic", "openai", "stability", "assemblyai", "apify", "firecrawl"}
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert tool["inputSchema"]["type"] == "object"
            assert "required" in tool["inputSchema"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 3 — tools/call with billing (happy path)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_tools_call_with_billing():
    wallet = _mock_wallet()
    tx = _mock_tx(cost=Decimal("0.001"))
    app.dependency_overrides[get_db] = _db_override(wallet, tx)
    app.dependency_overrides[require_api_key] = lambda: wallet

    tool_result = {"content_text": "hello world", "usage": {"input_tokens": 10, "output_tokens": 5}}
    wrapper = _mock_wrapper(
        estimate=Decimal("0.001"),
        result=(tool_result, Decimal("0.001")),
    )

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "anthropic",
                            "arguments": {
                                "messages": [{"role": "user", "content": "Hello"}],
                                "max_tokens": 10,
                            },
                        },
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 3
        result = body["result"]
        assert "content" in result
        assert len(result["content"]) == 1
        assert result["content"][0]["type"] == "text"
        assert "_meta" in result
        meta = result["_meta"]
        assert "transaction_id" in meta
        assert "cost_usdt" in meta
        assert "balance_remaining" in meta
        assert result.get("isError") is not True
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 4 — tools/call with insufficient balance → isError content
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_tools_call_insufficient_balance():
    wallet = _mock_wallet(balance=Decimal("0.000001"))
    app.dependency_overrides[get_db] = _db_override(wallet)
    app.dependency_overrides[require_api_key] = lambda: wallet

    wrapper = _mock_wrapper(estimate=Decimal("10"), result=({}, Decimal("10")))

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 4,
                        "method": "tools/call",
                        "params": {
                            "name": "anthropic",
                            "arguments": {"messages": [], "max_tokens": 10},
                        },
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        result = body["result"]
        assert result["isError"] is True
        assert len(result["content"]) == 1
        assert "Insufficient balance" in result["content"][0]["text"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 5 — unknown method returns JSON-RPC method-not-found error
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_unknown_method():
    wallet = _mock_wallet()
    app.dependency_overrides[get_db] = _db_override(wallet)
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "id": 5, "method": "resources/list", "params": {}},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32601
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 6 — JSON-RPC notification (no "id") returns 200 with empty body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_notification_no_response():
    wallet = _mock_wallet()
    app.dependency_overrides[get_db] = _db_override(wallet)
    app.dependency_overrides[require_api_key] = lambda: wallet

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 7 — tools/call with upstream error → isError, no wallet debit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mcp_tools_call_upstream_error_no_debit():
    wallet = _mock_wallet()
    tx = _mock_tx(cost=Decimal("0"))
    tx.status = TransactionStatus.upstream_error
    app.dependency_overrides[get_db] = _db_override(wallet, tx)
    app.dependency_overrides[require_api_key] = lambda: wallet

    wrapper = _mock_wrapper(estimate=Decimal("0.001"))
    wrapper.call = AsyncMock(side_effect=UpstreamError("API down", 503))

    try:
        with patch("src.routers.mcp._WRAPPERS", {"anthropic": wrapper}):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": 7,
                        "method": "tools/call",
                        "params": {
                            "name": "anthropic",
                            "arguments": {"messages": [], "max_tokens": 10},
                        },
                    },
                )
        assert resp.status_code == 200
        body = resp.json()
        result = body["result"]
        assert result["isError"] is True
        assert "Upstream error" in result["content"][0]["text"]
        # Balance must be untouched
        assert wallet.balance_usdt == Decimal("100")
    finally:
        app.dependency_overrides.clear()
