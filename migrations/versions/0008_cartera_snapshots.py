"""cartera_snapshots: cartera scoped por cuenta comitente, drop financial_snapshots.cartera

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cartera_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()"),
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_month", sa.Date(), nullable=False),
        sa.Column("nivel_detectado", sa.Integer(), nullable=False),
        sa.Column("posiciones", postgresql.JSONB(), nullable=False),
        sa.Column("rendimientos_netos_ars", sa.Numeric(precision=15, scale=4)),
        sa.Column("retenciones_ars", sa.Numeric(precision=15, scale=4)),
        sa.Column("delta_cartera_mes", postgresql.JSONB()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("account_id", "period_month", name="uq_cartera_snapshots_account_period"),
    )
    op.drop_column("financial_snapshots", "cartera")


def downgrade() -> None:
    op.add_column("financial_snapshots", sa.Column("cartera", postgresql.JSONB(), nullable=True))
    op.drop_table("cartera_snapshots")
