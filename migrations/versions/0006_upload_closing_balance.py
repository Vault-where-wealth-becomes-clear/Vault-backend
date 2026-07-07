"""uploads: add closing_balance_ars and closing_balance_usd for cross-period saldo check

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-03

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "uploads",
        sa.Column(
            "closing_balance_ars",
            sa.Numeric(precision=15, scale=4),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "uploads",
        sa.Column(
            "closing_balance_usd",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("uploads", "closing_balance_usd")
    op.drop_column("uploads", "closing_balance_ars")
