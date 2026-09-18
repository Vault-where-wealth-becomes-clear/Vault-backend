"""transactions: unique (upload_id, sort_order) to close the upload idempotency gap

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-18

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CONSTRAINT = "uq_transactions_upload_sort_order"


def upgrade() -> None:
    # Si el bug que esta migracion previene ya dejo duplicados, crear la
    # constraint falla con un error de Postgres imposible de interpretar a las
    # 3am. Se chequea antes y se falla nombrando los uploads afectados: borrar
    # transacciones de un producto financiero es una decision de una persona,
    # no de una migracion.
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT upload_id, COUNT(*) AS filas "
                "FROM ( "
                "  SELECT upload_id, sort_order FROM transactions "
                "  WHERE upload_id IS NOT NULL "
                "  GROUP BY upload_id, sort_order HAVING COUNT(*) > 1 "
                ") AS dup "
                "GROUP BY upload_id"
            )
        )
        .fetchall()
    )
    if duplicates:
        afectados = ", ".join(str(row[0]) for row in duplicates)
        raise RuntimeError(
            "No se puede crear la constraint de unicidad: estos uploads ya tienen "
            f"transacciones duplicadas por el bug de idempotencia: {afectados}. "
            "Revisa cada uno y decidi si borrar el upload y reprocesarlo o "
            "deduplicar a mano antes de volver a correr esta migracion."
        )

    op.create_unique_constraint(_CONSTRAINT, "transactions", ["upload_id", "sort_order"])


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "transactions", type_="unique")
