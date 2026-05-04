from decimal import Decimal
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.transaction import Transaction, TransactionStatus
from src.models.wallet import Wallet


class InsufficientBalanceError(Exception):
    pass


class MeteringService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_balance(self, wallet_id: uuid.UUID) -> Decimal:
        wallet = await self._db.get(Wallet, wallet_id)
        if wallet is None:
            raise ValueError(f"Wallet {wallet_id} not found")
        return Decimal(str(wallet.balance_usdt))

    async def check_balance(self, wallet_id: uuid.UUID, estimated_cost: Decimal) -> bool:
        balance = await self.get_balance(wallet_id)
        return balance >= estimated_cost

    async def debit(
        self,
        wallet_id: uuid.UUID,
        actual_cost: Decimal,
        fee_pct: Decimal,
        idempotency_key: str,
        tool: str,
        status: TransactionStatus,
        request_payload: Optional[dict] = None,
        response_meta: Optional[dict] = None,
    ) -> Transaction:
        # Idempotency: return existing transaction if key already used
        existing = await self._db.execute(
            select(Transaction).where(Transaction.idempotency_key == idempotency_key)
        )
        existing_tx = existing.scalar_one_or_none()
        if existing_tx is not None:
            return existing_tx

        fee = (actual_cost * fee_pct).quantize(Decimal("0.000001"))
        total = actual_cost + fee

        tx = Transaction(
            wallet_id=wallet_id,
            tool=tool,
            upstream_cost=actual_cost,
            fee_5pct=fee,
            total_cost=total,
            status=status,
            idempotency_key=idempotency_key,
            request_payload=request_payload,
            response_meta=response_meta,
        )
        self._db.add(tx)

        # Only debit wallet on successful calls — never on upstream_error
        if status == TransactionStatus.completed:
            wallet = await self._db.get(Wallet, wallet_id)
            if wallet is None:
                raise ValueError(f"Wallet {wallet_id} not found")
            balance = Decimal(str(wallet.balance_usdt))
            if balance < total:
                tx.status = TransactionStatus.insufficient_balance
                await self._db.commit()
                await self._db.refresh(tx)
                raise InsufficientBalanceError(
                    f"Balance {balance} < required {total}"
                )
            wallet.balance_usdt = balance - total

        await self._db.commit()
        await self._db.refresh(tx)
        return tx
