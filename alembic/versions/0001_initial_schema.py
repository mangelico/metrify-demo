"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", sa.String(255), nullable=False, unique=True),
        sa.Column("master_id", sa.String(255), nullable=True),
        sa.Column("balance_usdt", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_wallets_agent_id", "wallets", ["agent_id"])

    op.create_table(
        "transactions",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tool", sa.String(100), nullable=False),
        sa.Column("upstream_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("fee_5pct", sa.Numeric(18, 6), nullable=False),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "completed",
                "upstream_error",
                "insufficient_balance",
                name="transactionstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("request_payload", sa.JSON, nullable=True),
        sa.Column("response_meta", sa.JSON, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], name="fk_transactions_wallet_id"),
    )
    op.create_index("ix_transactions_wallet_id", "transactions", ["wallet_id"])
    op.create_index("ix_transactions_idempotency_key", "transactions", ["idempotency_key"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_transactions_created_at", "transactions")
    op.drop_index("ix_transactions_idempotency_key", "transactions")
    op.drop_index("ix_transactions_wallet_id", "transactions")
    op.drop_table("transactions")
    op.execute("DROP TYPE IF EXISTS transactionstatus")
    op.drop_index("ix_wallets_agent_id", "wallets")
    op.drop_table("wallets")
