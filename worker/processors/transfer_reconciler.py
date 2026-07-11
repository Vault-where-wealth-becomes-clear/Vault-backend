from datetime import timedelta
from decimal import Decimal

from sqlalchemy import select

from app.models.enums import CurrencyType
from app.models.transaction import Transaction

_UNRESOLVED_CATEGORIES = {"Transferencia interna", "Sin categoría"}
_DATE_TOLERANCE_DAYS = 3


def looks_like_transfer(description: str) -> bool:
    return "TRANSFER" in description.upper()


def _native_amount(txn: Transaction) -> Decimal:
    return txn.amount_usd if txn.currency == CurrencyType.USD else txn.amount_ars


def _amount_tolerance(txn: Transaction) -> Decimal:
    floor = Decimal("0.01") if txn.currency == CurrencyType.USD else Decimal("1")
    return max(floor, abs(_native_amount(txn)) * Decimal("0.005"))


def _is_match(a: Transaction, b: Transaction) -> bool:
    if a.account_id == b.account_id or a.currency != b.currency:
        return False
    amount_a, amount_b = _native_amount(a), _native_amount(b)
    if amount_a == 0 or (amount_a > 0) == (amount_b > 0):
        return False
    if abs(amount_a + amount_b) > _amount_tolerance(a):
        return False
    return abs((a.date - b.date).days) <= _DATE_TOLERANCE_DAYS


async def reconcile_internal_transfers(db, user_id) -> int:
    """
    Confirma "Transferencia interna" cruzando cuentas del propio usuario: una
    transacción con pinta de transferencia solo se puede confirmar como
    movimiento interno si aparece su contraparte (signo opuesto, mismo monto,
    misma moneda, fecha cercana) en OTRA cuenta del usuario. Si no aparece
    —porque esa cuenta todavía no está cargada, o porque simplemente no fue una
    transferencia interna— se deja en "Sin categoría" para que el usuario la
    categorice a mano vía la cola de revisión existente, en vez de asumir nada
    en ningún sentido.

    Se re-ejecuta completa (sobre todas las cuentas del usuario, no solo el
    upload nuevo) cada vez que se termina de procesar un archivo — así, cargar
    la cuenta que faltaba resuelve retroactivamente transferencias viejas que
    habían quedado en "Sin categoría", sin que el usuario tenga que hacer nada
    para ese caso.

    Nunca toca una transacción con is_corrected=True (el usuario ya la
    categorizó a mano) ni una que el LLM categorizó con confianza en otra cosa
    — el patrón de texto por sí solo no alcanza para pisar ese juicio.
    """
    candidates = (
        await db.scalars(
            select(Transaction).where(
                Transaction.user_id == user_id,
                Transaction.is_corrected.is_(False),
                Transaction.category.in_(_UNRESOLVED_CATEGORIES),
            )
        )
    ).all()
    candidates = [c for c in candidates if looks_like_transfer(c.description)]

    matches: dict[object, list[object]] = {c.id: [] for c in candidates}
    for i, a in enumerate(candidates):
        for b in candidates[i + 1 :]:
            if _is_match(a, b):
                matches[a.id].append(b.id)
                matches[b.id].append(a.id)

    by_id = {c.id: c for c in candidates}
    resolved = 0
    seen: set = set()
    for txn_id, others in matches.items():
        if txn_id in seen:
            continue
        if len(others) == 1:
            other_id = others[0]
            if len(matches[other_id]) == 1 and matches[other_id][0] == txn_id:
                by_id[txn_id].category = "Transferencia interna"
                by_id[txn_id].needs_review = False
                by_id[other_id].category = "Transferencia interna"
                by_id[other_id].needs_review = False
                seen.add(txn_id)
                seen.add(other_id)
                resolved += 2
                continue
        # Sin match único e inequívoco: no se adivina — queda para revisión manual.
        by_id[txn_id].category = "Sin categoría"
        by_id[txn_id].needs_review = True
        seen.add(txn_id)

    await db.flush()
    return resolved
