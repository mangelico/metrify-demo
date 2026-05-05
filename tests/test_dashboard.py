import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.database import get_db
from src.main import app
from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet


def _mock_wallet(agent_id="agent-001", balance=Decimal("100")):
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.agent_id = agent_id
    w.master_id = None
    w.balance_usdt = balance
    w.created_at = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    return w


def _mock_tx(tool="anthropic", status=TransactionStatus.completed, cost=Decimal("0.001")):
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.wallet_id = uuid.uuid4()
    tx.tool = tool
    tx.status = status
    tx.upstream_cost = cost
    tx.fee_5pct = cost * Decimal("0.05")
    tx.total_cost = cost + tx.fee_5pct
    tx.created_at = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    return tx


def _db_with_data(wallets=None, txs=None):
    """
    Mock DB for the main dashboard page.
    Query order: wallet_count, total_balance, tx_count, total_fees,
                 tool_stats, wallet_list, wallet_agg_stats.
    """
    wallets = wallets or []
    # txs kept for test compatibility but not rendered on main page
    _ = txs

    async def override():
        db = AsyncMock()
        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:   # wallet count
                result.scalar.return_value = len(wallets)
            elif call_count == 2: # total balance
                result.scalar.return_value = Decimal("50")
            elif call_count == 3: # tx count
                result.scalar.return_value = 5
            elif call_count == 4: # total fees
                result.scalar.return_value = Decimal("0.005")
            elif call_count == 5: # tool stats
                result.__iter__ = MagicMock(return_value=iter([]))
            elif call_count == 6: # wallet list
                scalars = MagicMock()
                scalars.all.return_value = wallets
                result.scalars.return_value = scalars
            else:                 # wallet agg stats
                result.__iter__ = MagicMock(return_value=iter([]))
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)
        yield db

    return override


@pytest.mark.asyncio
async def test_dashboard_returns_html():
    app.dependency_overrides[get_db] = _db_with_data()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Modelo Gateway" in resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_shows_wallet_list():
    wallets = [_mock_wallet("agent-alpha"), _mock_wallet("agent-beta")]
    app.dependency_overrides[get_db] = _db_with_data(wallets=wallets)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "agent-alpha" in resp.text
        assert "agent-beta" in resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_empty_state():
    app.dependency_overrides[get_db] = _db_with_data()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "No wallets yet" in resp.text
        assert "No transactions yet" in resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_wallet_detail_json():
    wallet = _mock_wallet("agent-drill")
    tx = _mock_tx(tool="openai", status=TransactionStatus.completed)

    async def db_override():
        db = AsyncMock()
        db.get = AsyncMock(return_value=wallet)

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if call_count == 1:  # last 10 transactions
                scalars = MagicMock()
                scalars.all.return_value = [tx]
                result.scalars.return_value = scalars
            else:                # usage by tool
                tool_row = MagicMock()
                tool_row.tool = "openai"
                tool_row.calls = 1
                tool_row.upstream_total = Decimal("0.001")
                tool_row.fees_total = Decimal("0.00005")
                tool_row.total = Decimal("0.00105")
                result.__iter__ = MagicMock(return_value=iter([tool_row]))
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)
        yield db

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/dashboard/wallet/{wallet.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["wallet"]["agent_id"] == "agent-drill"
        assert len(data["transactions_last_10"]) == 1
        assert data["transactions_last_10"][0]["tool"] == "openai"
        assert len(data["usage_by_tool"]) == 1
        assert data["usage_by_tool"][0]["tool"] == "openai"
        assert data["usage_by_tool"][0]["calls"] == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_wallet_detail_not_found():
    async def db_override():
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)
        yield db

    app.dependency_overrides[get_db] = db_override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/dashboard/wallet/{uuid.uuid4()}")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
