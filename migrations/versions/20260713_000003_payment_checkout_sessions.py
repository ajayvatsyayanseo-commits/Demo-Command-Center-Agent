"""Store restricted Cashfree checkout sessions separately and encrypted.

Revision ID: 20260713_000003
Revises: 20260713_000002
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260713_000003"
down_revision: str | None = "20260713_000002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_checkout_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_order_id", sa.Uuid(), nullable=False),
        sa.Column("session_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("key_reference", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_order_id"], ["payment_orders.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_order_id"),
    )


def downgrade() -> None:
    op.drop_table("payment_checkout_sessions")
