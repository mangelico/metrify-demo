import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    upstream_error = "upstream_error"
    insufficient_balance = "insufficient_balance"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )
    tool: Mapped[str] = mapped_column(String(100), nullable=False)
    upstream_cost: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    fee_5pct: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus), nullable=False, default=TransactionStatus.pending
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    request_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_transactions_wallet_id", "wallet_id"),
        Index("ix_transactions_idempotency_key", "idempotency_key"),
        Index("ix_transactions_created_at", "created_at"),
    )
