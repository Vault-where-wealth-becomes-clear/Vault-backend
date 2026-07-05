import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, BigInteger, Boolean, Date, Enum, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import UploadStatus


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    s3_key_pdf: Mapped[str] = mapped_column(String(500), nullable=False)
    s3_key_json: Mapped[str | None] = mapped_column(String(500))
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"), nullable=False, default=UploadStatus.pending
    )
    detected_bank: Mapped[str | None] = mapped_column(String(255))
    pending_mep: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requested_modules: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)), nullable=False, server_default=text("ARRAY['flujo_mensual']")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    opening_balance_ars: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, server_default=text("0")
    )
    opening_balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, server_default=text("0")
    )
    closing_balance_ars: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, server_default=text("0")
    )
    closing_balance_usd: Mapped[Decimal] = mapped_column(
        Numeric(15, 6), nullable=False, server_default=text("0")
    )
    llm_model_used: Mapped[str | None] = mapped_column(String(100))
    llm_input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    llm_output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    llm_thinking_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    llm_cache_read_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    llm_cache_creation_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    uploaded_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
    processed_at: Mapped[datetime | None] = mapped_column()
