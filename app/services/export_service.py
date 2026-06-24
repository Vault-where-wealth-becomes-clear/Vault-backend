import uuid
from io import BytesIO

import openpyxl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aws.s3 import S3Client
from app.models.transaction import Transaction


async def build_transactions_xlsx(db: AsyncSession, user_id: uuid.UUID) -> bytes:
    result = await db.scalars(
        select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.date)
    )

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Transacciones"
    sheet.append(["Fecha", "Descripción", "Monto ARS", "Monto USD", "Categoría", "Confianza"])

    for tx in result:
        sheet.append(
            [
                tx.date.isoformat(),
                tx.description,
                float(tx.amount_ars),
                float(tx.amount_usd) if tx.amount_usd is not None else None,
                tx.category,
                float(tx.confidence) if tx.confidence is not None else None,
            ]
        )

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def export_transactions_to_s3(db: AsyncSession, s3: S3Client, user_id: uuid.UUID, period_month: str) -> str:
    content = await build_transactions_xlsx(db, user_id)
    key = f"exports/{user_id}/{period_month}/export.xlsx"
    s3.client.put_object(
        Bucket=s3.bucket,
        Key=key,
        Body=content,
        ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    return key
