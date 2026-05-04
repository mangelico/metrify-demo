import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet
from src.services.metering import InsufficientBalanceError, MeteringService


def _mock_wallet(balance: Decimal) -> MagicMock:
    w = MagicMock(spec=Wallet)
    w.id = uuid.uuid4()
    w.balance_usdt = balance
    return w


def _mock_db(wallet=None, existing_tx=None) -> AsyncMock:
    db = AsyncMock()
    db.get = AsyncMock(return_value=wallet)

    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_tx
    db.execute = AsyncMock(return_value=result)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


WALLET_ID = uuid.uuid4()
FEE = Decimal("0.05")


@pytest.mark.asyncio
async def test_get_balance():
    wallet = _mock_wallet(Decimal("100.000000"))
    db = _mock_db(wallet=wallet)
    svc = MeteringService(db)
    balance = await svc.get_balance(wallet.id)
    assert balance == Decimal("100.000000")


@pytest.mark.asyncio
async def test_check_balance_sufficient():
    wallet = _mock_wallet(Decimal("10.000000"))
    db = _mock_db(wallet=wallet)
    svc = MeteringService(db)
    assert await svc.check_balance(wallet.id, Decimal("5")) is True


@pytest.mark.asyncio
async def test_check_balance_insufficient():
    wallet = _mock_wallet(Decimal("1.000000"))
    db = _mock_db(wallet=wallet)
    svc = MeteringService(db)
    assert await svc.check_balance(wallet.id, Decimal("5")) is False


@pytest.mark.asyncio
async def test_debit_completed_debits_wallet():
    wallet = _mock_wallet(Decimal("10.000000"))
    db = _mock_db(wallet=wallet)
    svc = MeteringService(db)

    tx = await svc.debit(
        wallet_id=wallet.id,
        actual_cost=Decimal("2.000000"),
        fee_pct=FEE,
        idempotency_key="key-001",
        tool="anthropic",
        status=TransactionStatus.completed,
    )

    # wallet balance must be reduced by total (cost + fee)
    expected_total = Decimal("2.000000") + Decimal("2.000000") * FEE
    assert wallet.balance_usdt == Decimal("10.000000") - expected_total
    db.commit.assert_called()


@pytest.mark.asyncio
async def test_debit_upstream_error_no_debit():
    wallet = _mock_wallet(Decimal("10.000000"))
    original_balance = wallet.balance_usdt
    db = _mock_db(wallet=wallet)
    svc = MeteringService(db)

    tx = await svc.debit(
        wallet_id=wallet.id,
        actual_cost=Decimal("2.000000"),
        fee_pct=FEE,
        idempotency_key="key-002",
        tool="anthropic",
        status=TransactionStatus.upstream_error,
    )

    # balance unchanged on upstream error
    assert wallet.balance_usdt == original_balance
    assert tx.status == TransactionStatus.upstream_error


@pytest.mark.asyncio
async def test_debit_insufficient_balance_raises():
    wallet = _mock_wallet(Decimal("0.001000"))
    db = _mock_db(wallet=wallet)
    svc = MeteringService(db)

    with pytest.raises(InsufficientBalanceError):
        await svc.debit(
            wallet_id=wallet.id,
            actual_cost=Decimal("5.000000"),
            fee_pct=FEE,
            idempotency_key="key-003",
            tool="anthropic",
            status=TransactionStatus.completed,
        )


@pytest.mark.asyncio
async def test_debit_idempotency_no_double_debit():
    existing_tx = MagicMock(spec=Transaction)
    existing_tx.idempotency_key = "key-dup"

    wallet = _mock_wallet(Decimal("10.000000"))
    db = _mock_db(wallet=wallet, existing_tx=existing_tx)
    svc = MeteringService(db)

    result = await svc.debit(
        wallet_id=wallet.id,
        actual_cost=Decimal("2.000000"),
        fee_pct=FEE,
        idempotency_key="key-dup",
        tool="anthropic",
        status=TransactionStatus.completed,
    )

    # returns existing transaction, no new add, no wallet mutation
    assert result is existing_tx
    db.add.assert_not_called()
    assert wallet.balance_usdt == Decimal("10.000000")
