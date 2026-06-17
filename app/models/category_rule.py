import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import RuleSource


class CategoryRule(Base):
    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_category_rules_user_keyword"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[RuleSource] = mapped_column(
        Enum(RuleSource, name="rule_source"), nullable=False, default=RuleSource.user
    )
    times_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
