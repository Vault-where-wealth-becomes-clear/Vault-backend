"""uploads: add llm token usage tracking columns

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("uploads", sa.Column("llm_model_used", sa.String(length=100)))
    for col in (
        "llm_input_tokens",
        "llm_output_tokens",
        "llm_thinking_tokens",
        "llm_cache_read_tokens",
        "llm_cache_creation_tokens",
    ):
        op.add_column(
            "uploads",
            sa.Column(col, sa.BigInteger(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for col in (
        "llm_cache_creation_tokens",
        "llm_cache_read_tokens",
        "llm_thinking_tokens",
        "llm_output_tokens",
        "llm_input_tokens",
        "llm_model_used",
    ):
        op.drop_column("uploads", col)
