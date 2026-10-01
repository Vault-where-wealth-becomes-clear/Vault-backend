"""SQS garantiza at-least-once, no exactly-once. El ledger de un usuario no
puede duplicarse porque un mensaje se haya entregado dos veces."""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models.account import Account
from app.models.enums import AccountType, CurrencyType, UploadStatus
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from worker import processing


class _BorrowedSession:
    """Le presta la sesion del test a `process_upload`, que normalmente abre la
    suya con `AsyncSessionLocal`, sin cerrarla al salir del bloque."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def _make_upload(db, status: UploadStatus = UploadStatus.pending) -> Upload:
    user = User(email=f"{uuid.uuid4()}@test.com", cognito_sub=str(uuid.uuid4()))
    db.add(user)
    await db.flush()

    account = Account(
        user_id=user.id,
        name="Caja de ahorro",
        account_type=AccountType.checking_ars,
        currency=CurrencyType.ARS,
    )
    db.add(account)
    await db.flush()

    upload = Upload(
        user_id=user.id,
        account_id=account.id,
        s3_key_pdf=f"{user.id}/extracto.pdf",
        period_month=date(2026, 7, 1),
        status=status,
    )
    db.add(upload)
    await db.flush()
    return upload


def _txn(description: str, amount: str) -> dict:
    return {
        "date": "2026-07-05",
        "description": description,
        "amount_ars": Decimal(amount),
        "amount_usd": None,
        "currency": "ARS",
        "category": "Servicios",
        "confidence": 0.95,
        "needs_review": False,
    }


async def _count_transactions(db, upload_id: uuid.UUID) -> int:
    return await db.scalar(
        select(func.count()).select_from(Transaction).where(Transaction.upload_id == upload_id)
    )


@pytest.mark.parametrize("estado", [UploadStatus.done, UploadStatus.review])
async def test_a_finished_upload_is_not_reprocessed(db, monkeypatch, estado):
    """Si `delete_message` falla despues de un procesamiento exitoso, el
    mensaje vuelve a la cola con el trabajo ya hecho. Reprocesarlo duplicaria
    el ledger y volveria a pagar la llamada al LLM."""
    upload = await _make_upload(db, status=estado)
    monkeypatch.setattr(processing, "AsyncSessionLocal", lambda: _BorrowedSession(db))

    # Si no cortara temprano, seguiria hasta S3 y el LLM y reventaria aca.
    await processing.process_upload(
        {
            "upload_id": str(upload.id),
            "user_id": str(upload.user_id),
            "account_type": AccountType.checking_ars.value,
            "period_month": "2026-07-01",
            "s3_key_pdf": upload.s3_key_pdf,
        }
    )

    assert upload.status == estado, "el estado no se toca"
    assert await _count_transactions(db, upload.id) == 0


async def test_rerunning_save_transactions_replaces_instead_of_duplicating(db):
    """Un upload que quedo a medias y se reintenta tiene que reemplazar sus
    filas, no acumular encima de las de la corrida anterior."""
    upload = await _make_upload(db)
    transacciones = [_txn("Luz", "-15000.00"), _txn("Sueldo", "900000.00")]

    await processing._save_transactions(
        db, upload, [dict(t) for t in transacciones], "checking_ars"
    )
    assert await _count_transactions(db, upload.id) == 2

    await processing._save_transactions(
        db, upload, [dict(t) for t in transacciones], "checking_ars"
    )
    assert await _count_transactions(db, upload.id) == 2, "el reintento reemplaza, no duplica"


async def test_the_database_rejects_a_duplicate_row_for_the_same_upload(db):
    """La ultima linea de defensa: si dos workers procesan el mismo upload a la
    vez —la visibility timeout vence en medio de una llamada larga al LLM— el
    segundo commit muere contra la constraint en vez de duplicar el ledger."""
    upload = await _make_upload(db)

    for _ in range(2):
        db.add(
            Transaction(
                upload_id=upload.id,
                user_id=upload.user_id,
                account_id=upload.account_id,
                date=date(2026, 7, 5),
                description="Luz",
                amount_ars=Decimal("-15000.00"),
                currency=CurrencyType.ARS,
                needs_review=False,
                sort_order=0,
            )
        )

    # Savepoint: contiene el fallo esperado para que la sesion del test
    # quede usable y el teardown no chille.
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.flush()
