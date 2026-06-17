from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.s3 import S3Client, get_s3
from app.database import get_db
from app.middleware.plans import require_plan
from app.models.user import User
from app.services.export_service import export_transactions_to_s3

router = APIRouter(prefix="/exports", tags=["exports"])


class ExportXlsxResponse(BaseModel):
    download_url: str


@router.post("/xlsx", response_model=ExportXlsxResponse)
async def export_xlsx(
    current_user: User = Depends(require_plan("pro", "family")),
    db: AsyncSession = Depends(get_db),
    s3: S3Client = Depends(get_s3),
):
    period = date.today().strftime("%Y-%m")
    key = await export_transactions_to_s3(db, s3, current_user.id, period)
    download_url = await s3.generate_presigned_get_url(key)
    return ExportXlsxResponse(download_url=download_url)
