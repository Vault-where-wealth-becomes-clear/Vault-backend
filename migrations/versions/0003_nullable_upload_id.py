"""transactions: make upload_id nullable for manual entries

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-30

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("transactions", "upload_id", existing_type=sa.UUID(), nullable=True)


def downgrade() -> None:
    # Solo es seguro si no existen filas con upload_id = NULL
    op.alter_column("transactions", "upload_id", existing_type=sa.UUID(), nullable=False)
