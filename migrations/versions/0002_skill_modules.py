"""skill modules: upload_module_requests, financial_snapshots

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-22

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


skill_module = postgresql.ENUM(
    "flujo_mensual",
    "categorizacion_gasto",
    "flujo_periodo",
    "cuenta_comitente",
    "tablero_general",
    "proyeccion_patrimonial",
    "compromisos_futuros",
    name="skill_module",
    create_type=False,
)
upload_status = postgresql.ENUM(
    "pending", "processing", "review", "done", "error", name="upload_status", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()
    skill_module.create(bind, checkfirst=True)

    op.add_column(
        "uploads",
        sa.Column(
            "requested_modules",
            postgresql.ARRAY(sa.String(50)),
            nullable=False,
            server_default=sa.text("ARRAY['flujo_mensual']"),
        ),
    )

    op.create_table(
        "upload_module_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            primary_key=True,
        ),
        sa.Column(
            "upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("uploads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("module", skill_module, nullable=False),
        sa.Column("status", upload_status, nullable=False, server_default="pending"),
        sa.Column("result_json", postgresql.JSONB),
        sa.Column("error_message", sa.Text),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("upload_id", "module", name="uq_upload_module_requests_upload_module"),
    )

    op.create_table(
        "financial_snapshots",
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
        sa.Column("period_month", sa.Date, nullable=False),
        sa.Column("flujo_mensual", postgresql.JSONB),
        sa.Column("categorizacion", postgresql.JSONB),
        sa.Column("flujo_periodo", postgresql.JSONB),
        sa.Column("cartera", postgresql.JSONB),
        sa.Column("tablero_general", postgresql.JSONB),
        sa.Column("proyeccion", postgresql.JSONB),
        sa.Column("compromisos", postgresql.JSONB),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("user_id", "period_month", name="uq_financial_snapshots_user_period"),
    )

    op.create_index("idx_module_requests_upload", "upload_module_requests", ["upload_id"])
    op.create_index("idx_snapshots_user_period", "financial_snapshots", ["user_id", "period_month"])


def downgrade() -> None:
    op.drop_index("idx_snapshots_user_period", table_name="financial_snapshots")
    op.drop_index("idx_module_requests_upload", table_name="upload_module_requests")

    op.drop_table("financial_snapshots")
    op.drop_table("upload_module_requests")

    op.drop_column("uploads", "requested_modules")

    bind = op.get_bind()
    skill_module.drop(bind, checkfirst=True)
