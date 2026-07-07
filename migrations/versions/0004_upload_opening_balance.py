"""uploads: add opening_balance_ars and opening_balance_usd for multi-period split

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "uploads",
        sa.Column(
            "opening_balance_ars",
            sa.Numeric(precision=15, scale=4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "uploads",
        sa.Column(
            "opening_balance_usd",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("uploads", "opening_balance_usd")
    op.drop_column("uploads", "opening_balance_ars")
