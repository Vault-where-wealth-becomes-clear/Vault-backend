"""exchange_rates: scope per user instead of one global table

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_OLD_UNIQUE = "exchange_rates_period_month_key"
_NEW_UNIQUE = "uq_exchange_rates_user_period"


def upgrade() -> None:
    op.add_column(
        "exchange_rates",
        sa.Column("user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Hay que soltarla antes del backfill: el mismo periodo pasa a existir una
    # vez por usuario.
    op.drop_constraint(_OLD_UNIQUE, "exchange_rates", type_="unique")

    # Cada tasa global pasa a ser una tasa propia de cada usuario, para que
    # nadie pierda el TC que ya tenia declarado ni quede con uploads que de
    # golpe no pueden convertirse. El SELECT trabaja sobre el snapshot previo
    # al INSERT, asi que las filas nuevas no se re-seleccionan.
    op.execute(
        sa.text(
            "INSERT INTO exchange_rates (user_id, period_month, mep_rate, source, set_at) "
            "SELECT u.id, e.period_month, e.mep_rate, e.source, e.set_at "
            "FROM exchange_rates e CROSS JOIN users u "
            "WHERE e.user_id IS NULL"
        )
    )
    op.execute(sa.text("DELETE FROM exchange_rates WHERE user_id IS NULL"))

    op.alter_column("exchange_rates", "user_id", nullable=False)
    op.create_foreign_key(
        "fk_exchange_rates_user_id",
        "exchange_rates",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(_NEW_UNIQUE, "exchange_rates", ["user_id", "period_month"])


def downgrade() -> None:
    # Volver a una tabla global es necesariamente con perdida: de las N filas
    # por periodo hay que quedarse con una sola. Se conserva la declarada mas
    # recientemente, que es la mejor aproximacion al valor "vigente".
    op.drop_constraint(_NEW_UNIQUE, "exchange_rates", type_="unique")
    op.drop_constraint("fk_exchange_rates_user_id", "exchange_rates", type_="foreignkey")
    op.execute(
        sa.text(
            "DELETE FROM exchange_rates e USING exchange_rates mas_nueva "
            "WHERE e.period_month = mas_nueva.period_month "
            "AND (e.set_at, e.id) < (mas_nueva.set_at, mas_nueva.id)"
        )
    )
    op.drop_column("exchange_rates", "user_id")
    op.create_unique_constraint(_OLD_UNIQUE, "exchange_rates", ["period_month"])
