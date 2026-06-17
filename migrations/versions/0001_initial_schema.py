"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-10

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


plan_type = postgresql.ENUM("free", "pro", "family", name="plan_type", create_type=False)
account_type = postgresql.ENUM(
    "credit_card_ars",
    "credit_card_usd",
    "checking_ars",
    "checking_usd",
    "broker",
    "crypto",
    "cash",
    "savings_box",
    name="account_type",
    create_type=False,
)
upload_status = postgresql.ENUM(
    "pending", "processing", "review", "done", "error", name="upload_status", create_type=False
)
currency_type = postgresql.ENUM("ARS", "USD", name="currency_type", create_type=False)
rule_source = postgresql.ENUM("user", "ai", name="rule_source", create_type=False)
mep_source = postgresql.ENUM("manual", "api", name="mep_source", create_type=False)


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    bind = op.get_bind()
    plan_type.create(bind, checkfirst=True)
    account_type.create(bind, checkfirst=True)
    upload_status.create(bind, checkfirst=True)
    currency_type.create(bind, checkfirst=True)
    rule_source.create(bind, checkfirst=True)
    mep_source.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("name", sa.String(255)),
        sa.Column("cognito_sub", sa.String(255), nullable=False, unique=True),
        sa.Column("plan", plan_type, nullable=False, server_default="free"),
        sa.Column("base_currency", currency_type, nullable=False, server_default="USD"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_type", account_type, nullable=False),
        sa.Column("institution", sa.String(255)),
        sa.Column("currency", currency_type, nullable=False, server_default="ARS"),
        sa.Column("current_balance", sa.Numeric(14, 2), server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("period_month", sa.Date, nullable=False, unique=True),
        sa.Column("mep_rate", sa.Numeric(10, 2), nullable=False),
        sa.Column("source", mep_source, nullable=False, server_default="manual"),
        sa.Column("set_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("s3_key_pdf", sa.String(500), nullable=False),
        sa.Column("s3_key_json", sa.String(500)),
        sa.Column("period_month", sa.Date, nullable=False),
        sa.Column("status", upload_status, nullable=False, server_default="pending"),
        sa.Column("detected_bank", sa.String(255)),
        sa.Column("pending_mep", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("error_message", sa.Text),
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True)),
    )

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("amount_ars", sa.Numeric(14, 2), nullable=False),
        sa.Column("amount_usd", sa.Numeric(14, 4)),
        sa.Column("currency", currency_type, nullable=False, server_default="ARS"),
        sa.Column("category", sa.String(100)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("needs_review", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("is_corrected", sa.Boolean, nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "installments",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("current_installment", sa.Integer, nullable=False),
        sa.Column("total_installments", sa.Integer, nullable=False),
        sa.Column("amount_per_installment", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", currency_type, nullable=False, server_default="ARS"),
        sa.Column("next_due_date", sa.Date),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    op.create_table(
        "category_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keyword", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("source", rule_source, nullable=False, server_default="user"),
        sa.Column("times_applied", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.UniqueConstraint("user_id", "keyword", name="uq_category_rules_user_keyword"),
    )

    op.create_table(
        "category_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("uuid_generate_v4()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("limit_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", currency_type, nullable=False, server_default="ARS"),
        sa.Column("alert_at_pct", sa.Integer, nullable=False, server_default="80"),
        sa.UniqueConstraint("user_id", "category", name="uq_category_limits_user_category"),
    )

    op.create_index("idx_transactions_user_date", "transactions", ["user_id", sa.text("date DESC")])
    op.create_index("idx_transactions_upload", "transactions", ["upload_id"])
    op.create_index(
        "idx_transactions_needs_review",
        "transactions",
        ["upload_id"],
        postgresql_where=sa.text("needs_review = TRUE"),
    )
    op.create_index("idx_uploads_user_status", "uploads", ["user_id", "status"])
    op.create_index("idx_installments_user", "installments", ["user_id", "next_due_date"])
    op.create_index("idx_category_rules_user_keyword", "category_rules", ["user_id", "keyword"])


def downgrade() -> None:
    op.drop_index("idx_category_rules_user_keyword", table_name="category_rules")
    op.drop_index("idx_installments_user", table_name="installments")
    op.drop_index("idx_uploads_user_status", table_name="uploads")
    op.drop_index("idx_transactions_needs_review", table_name="transactions")
    op.drop_index("idx_transactions_upload", table_name="transactions")
    op.drop_index("idx_transactions_user_date", table_name="transactions")

    op.drop_table("category_limits")
    op.drop_table("category_rules")
    op.drop_table("installments")
    op.drop_table("transactions")
    op.drop_table("uploads")
    op.drop_table("exchange_rates")
    op.drop_table("accounts")
    op.drop_table("users")

    bind = op.get_bind()
    mep_source.drop(bind, checkfirst=True)
    rule_source.drop(bind, checkfirst=True)
    currency_type.drop(bind, checkfirst=True)
    upload_status.drop(bind, checkfirst=True)
    account_type.drop(bind, checkfirst=True)
    plan_type.drop(bind, checkfirst=True)
