"""api_keys table

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("wallet_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], name="fk_api_keys_wallet_id"),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_wallet_id", "api_keys", ["wallet_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_wallet_id", "api_keys")
    op.drop_index("ix_api_keys_key_hash", "api_keys")
    op.drop_table("api_keys")
