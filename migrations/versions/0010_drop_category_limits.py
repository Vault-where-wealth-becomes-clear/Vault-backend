"""drop category_limits: dead scaffolding, never wired to any router/service

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

currency_type = postgresql.ENUM("ARS", "USD", name="currency_type", create_type=False)


def upgrade() -> None:
    op.drop_table("category_limits")


def downgrade() -> None:
    op.create_table(
        "category_limits",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("limit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", currency_type, nullable=False, server_default="ARS"),
        sa.Column("alert_at_pct", sa.Integer, nullable=False, server_default="80"),
        sa.UniqueConstraint("user_id", "category", name="uq_category_limits_user_category"),
    )
