import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.database import get_db
from src.main import app
from src.models.wallet import Wallet


def _mock_wallet(agent_id="agent_001", balance=Decimal("0")):
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.agent_id = agent_id
    w.master_id = None
    w.balance_usdt = balance
    return w


def _make_db(wallet=None):
    db = AsyncMock()
    db.get = AsyncMock(return_value=wallet)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_get_wallet_not_found():
    db = _make_db(wallet=None)

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/wallets/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.json()["detail"]["error"] == "wallet_not_found"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_wallet_found():
    wallet = _mock_wallet(balance=Decimal("50.000000"))
    db = _make_db(wallet=wallet)

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/wallets/{wallet.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "agent_001"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_topup_wallet_happy():
    wallet = _mock_wallet(balance=Decimal("10.000000"))
    db = _make_db(wallet=wallet)

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/wallets/{wallet.id}/topup",
                json={"amount": "5.5"},
                headers={"X-Admin-Token": "test-admin-token"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert Decimal(data["added"]) == Decimal("5.5")
        assert Decimal(data["balance_usdt"]) == Decimal("15.5")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_topup_wallet_not_found():
    db = _make_db(wallet=None)

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/wallets/{uuid.uuid4()}/topup",
                json={"amount": "10"},
                headers={"X-Admin-Token": "test-admin-token"},
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_topup_invalid_amount():
    db = _make_db()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/wallets/{uuid.uuid4()}/topup",
                json={"amount": "-1"},
                headers={"X-Admin-Token": "test-admin-token"},
            )
        assert resp.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_topup_missing_admin_token():
    db = _make_db()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/wallets/{uuid.uuid4()}/topup", json={"amount": "10"}
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_topup_wrong_admin_token():
    db = _make_db()

    async def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                f"/wallets/{uuid.uuid4()}/topup",
                json={"amount": "10"},
                headers={"X-Admin-Token": "wrong-token"},
            )
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
