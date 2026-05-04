import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.database import get_db
from src.main import app
from src.models.transaction import Transaction, TransactionStatus


def _mock_tx(tool="anthropic", status=TransactionStatus.completed, cost=Decimal("0.001")):
    tx = MagicMock(spec=Transaction)
    tx.id = uuid.uuid4()
    tx.tool = tool
    tx.status = status
    tx.upstream_cost = cost
    tx.fee_5pct = cost * Decimal("0.05")
    tx.total_cost = cost + tx.fee_5pct
    tx.created_at = datetime(2026, 5, 5, 12, 0, tzinfo=timezone.utc)
    return tx


def _db_with_data(txs=None):
    txs = txs or []

    async def override():
        db = AsyncMock()

        call_count = 0

        async def execute_side_effect(stmt):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            # Return scalars in order: wallet_count, total_balance, tx_count, total_fees, tool_rows, tx_rows
            if call_count == 1:   # wallet count
                result.scalar.return_value = 2
            elif call_count == 2: # total balance
                result.scalar.return_value = Decimal("50")
            elif call_count == 3: # tx count
                result.scalar.return_value = len(txs)
            elif call_count == 4: # total fees
                result.scalar.return_value = Decimal("0.005")
            elif call_count == 5: # tool stats
                result.__iter__ = MagicMock(return_value=iter([]))
            else:                 # transactions
                scalars = MagicMock()
                scalars.all.return_value = txs
                result.scalars.return_value = scalars
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
async def test_dashboard_shows_transactions():
    txs = [_mock_tx(), _mock_tx(tool="openai", status=TransactionStatus.upstream_error)]
    app.dependency_overrides[get_db] = _db_with_data(txs=txs)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "anthropic" in resp.text
        assert "openai" in resp.text
        assert "upstream_error" in resp.text
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_empty_state():
    app.dependency_overrides[get_db] = _db_with_data(txs=[])
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/dashboard")
        assert resp.status_code == 200
        assert "No transactions yet" in resp.text
    finally:
        app.dependency_overrides.clear()
