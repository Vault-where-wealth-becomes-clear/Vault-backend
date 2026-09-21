"""Un PDF consolidado con varios meses se parte en un upload por mes, y el
saldo de cierre real de cada mes encadena el saldo inicial del siguiente.

Es la logica mas cara de equivocarse del pipeline: antes de que existiera el
encadenado, cada mes despues del primero arrancaba en 0 y el patrimonio del
usuario quedaba mal a partir de ahi.
"""

import json
import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.account import Account
from app.models.enums import AccountType, CurrencyType, UploadStatus
from app.models.transaction import Transaction
from app.models.upload import Upload
from app.models.user import User
from worker import processing

# Dos meses en un solo PDF. Los saldos de la derecha son los que imprime el
# banco: 100.000 de apertura, y cada linea deja el saldo resultante.
_EXTRACTO_DOS_MESES = """
MOVIMIENTOS
05/06  SUELDO              500.000,00     600.000,00
20/06  ALQUILER           -300.000,00     300.000,00
05/07  SUELDO              500.000,00     800.000,00
20/07  ALQUILER           -300.000,00     500.000,00
"""

_RESPUESTA_LLM = json.dumps(
    {
        "transacciones": [
            {
                "date": "2026-06-05",
                "description": "SUELDO",
                "amount": 500000.0,
                "currency": "ARS",
                "category": "Ingresos",
                "confidence": 0.98,
            },
            {
                "date": "2026-06-20",
                "description": "ALQUILER",
                "amount": -300000.0,
                "currency": "ARS",
                "category": "Vivienda",
                "confidence": 0.98,
            },
            {
                "date": "2026-07-05",
                "description": "SUELDO",
                "amount": 500000.0,
                "currency": "ARS",
                "category": "Ingresos",
                "confidence": 0.98,
            },
            {
                "date": "2026-07-20",
                "description": "ALQUILER",
                "amount": -300000.0,
                "currency": "ARS",
                "category": "Vivienda",
                "confidence": 0.98,
            },
        ],
        "flujo_mensual": {
            "libro_diario": {
                "Caja de ahorro": {
                    "saldo_inicial": 100000,
                    "saldo_final": 500000,
                    "reconciliacion_ok": True,
                }
            }
        },
    }
)

_USO_LLM = {
    "model": "claude-test",
    "input_tokens": 1000,
    "output_tokens": 500,
    "thinking_tokens": 0,
    "cache_read_tokens": 0,
    "cache_creation_tokens": 0,
}


class _BorrowedSession:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


class _FakeS3:
    async def download_bytes(self, key: str) -> bytes:
        return b"%PDF-falso"

    async def delete_object(self, key: str) -> None:
        pass


@pytest.fixture
def pipeline_sin_dependencias_externas(db, monkeypatch):
    """Reemplaza S3, la extraccion de texto y el LLM. Todo lo demas —split por
    mes, verificacion contra el ledger, encadenado y reconciliacion— corre de
    verdad, que es lo que este test mide."""
    monkeypatch.setattr(processing, "AsyncSessionLocal", lambda: _BorrowedSession(db))
    monkeypatch.setattr(processing, "S3Client", _FakeS3)
    monkeypatch.setattr(processing, "extract_text", lambda data, key: _EXTRACTO_DOS_MESES)
    monkeypatch.setattr(
        processing, "call_llm_with_skill", lambda *a, **kw: (_RESPUESTA_LLM, _USO_LLM)
    )
    # El TC no es lo que se testea aca y su lookup cambia de forma segun el
    # scoping por usuario: se fija para que el test mida el split y nada mas.
    monkeypatch.setattr(processing, "_get_mep_rate", _mep_fijo)


async def _mep_fijo(*args, **kwargs) -> Decimal:
    return Decimal("1000")


async def _armar_upload(db) -> tuple[User, Account, Upload]:
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
        s3_key_pdf=f"uploads/{user.id}/2026-06/consolidado.pdf",
        period_month=date(2026, 6, 1),
        status=UploadStatus.pending,
        requested_modules=["flujo_mensual"],
    )
    db.add(upload)
    await db.flush()
    return user, account, upload


async def _correr(db, user: User, account: Account, upload: Upload) -> list[Upload]:
    await processing.process_upload(
        {
            "upload_id": str(upload.id),
            "user_id": str(user.id),
            "account_type": account.account_type.value,
            "period_month": "2026-06-01",
            "s3_key_pdf": upload.s3_key_pdf,
            "requested_modules": ["flujo_mensual"],
        }
    )
    resultado = await db.scalars(
        select(Upload).where(Upload.account_id == account.id).order_by(Upload.period_month)
    )
    return list(resultado)


async def test_a_two_month_pdf_becomes_one_upload_per_month(db, pipeline_sin_dependencias_externas):
    user, account, upload = await _armar_upload(db)

    uploads = await _correr(db, user, account, upload)

    assert [u.period_month for u in uploads] == [date(2026, 6, 1), date(2026, 7, 1)]
    assert uploads[0].id == upload.id, "el primer mes reusa el upload original"


async def test_each_month_keeps_only_its_own_transactions(db, pipeline_sin_dependencias_externas):
    user, account, upload = await _armar_upload(db)

    uploads = await _correr(db, user, account, upload)

    for u in uploads:
        filas = list(await db.scalars(select(Transaction).where(Transaction.upload_id == u.id)))
        assert len(filas) == 2, f"{u.period_month} tiene que quedarse con sus dos movimientos"


async def test_the_second_month_opens_at_the_first_months_printed_closing_balance(
    db, pipeline_sin_dependencias_externas
):
    """El bug que esto previene: sin encadenar, julio arrancaba en 0 y todo el
    patrimonio a partir de ahi quedaba mal."""
    user, account, upload = await _armar_upload(db)

    junio, julio = await _correr(db, user, account, upload)

    assert junio.opening_balance_ars == Decimal("100000.00"), "sale del libro_diario del PDF"
    assert junio.closing_balance_ars == Decimal("300000.00"), "saldo impreso de la ultima linea"
    assert julio.opening_balance_ars == Decimal("300000.00"), "encadena con el cierre de junio"
    assert julio.closing_balance_ars == Decimal("500000.00")


async def test_both_months_reconcile_and_close_clean(db, pipeline_sin_dependencias_externas):
    """creditos - debitos + saldo anterior tiene que dar el saldo impreso. Si
    no diera, el upload quedaria en `review` con el motivo escrito."""
    user, account, upload = await _armar_upload(db)

    uploads = await _correr(db, user, account, upload)

    for u in uploads:
        assert u.status == UploadStatus.done, f"{u.period_month}: {u.error_message}"
        assert u.error_message is None


async def test_the_llm_token_usage_is_recorded_on_the_upload(
    db, pipeline_sin_dependencias_externas
):
    user, account, upload = await _armar_upload(db)

    uploads = await _correr(db, user, account, upload)

    assert uploads[0].llm_model_used == "claude-test"
    assert uploads[0].llm_input_tokens == 1000
