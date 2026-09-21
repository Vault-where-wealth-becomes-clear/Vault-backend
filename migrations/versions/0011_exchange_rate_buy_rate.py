"""exchange_rates: add buy_rate (compra) alongside the existing sell rate

mep_rate sigue significando "venta" — es el que se usa en todos los
calculos existentes (worker, dashboard). buy_rate es solo informativo,
para mostrar ambos valores como pide la ingesta automatica de MEP (#17).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-21

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exchange_rates",
        sa.Column("buy_rate", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("exchange_rates", "buy_rate")
