import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import SkillModule, UploadStatus


class UploadModuleRequest(Base):
    __tablename__ = "upload_module_requests"
    __table_args__ = (UniqueConstraint("upload_id", "module", name="uq_upload_module_requests_upload_module"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()")
    )
    upload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[SkillModule] = mapped_column(Enum(SkillModule, name="skill_module"), nullable=False)
    status: Mapped[UploadStatus] = mapped_column(
        Enum(UploadStatus, name="upload_status"), nullable=False, default=UploadStatus.pending
    )
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=text("NOW()"))
