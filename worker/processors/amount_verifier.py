import re
from decimal import Decimal

_LINE_RE = re.compile(
    r"^\d{2}-[A-Za-z]{3}-\d{2}\s+.*?(?P<cupon>\d{5,7})\s+(?P<amount>-?[0-9.]*[0-9],[0-9]{2})\s*$"
)


def _parse_ar_number(raw: str) -> Decimal:
    return Decimal(raw.replace(".", "").replace(",", "."))


def _extract_printed_amounts(text: str) -> dict[str, Decimal]:
    """cupón -> monto impreso (valor absoluto), leído directo del texto del extracto."""
    printed: dict[str, Decimal] = {}
    for line in text.splitlines():
        m = _LINE_RE.match(line.strip())
        if not m:
            continue
        printed[m.group("cupon")] = abs(_parse_ar_number(m.group("amount")))
    return printed


def verify_and_correct_amounts(transactions: list[dict], extracted_text: str) -> list[dict]:
    """
    Corrige `amount` (y `installments.amount_per`) contra el número impreso en el
    extracto original, usando el cupón como clave de cruce. El LLM puede — y ya
    lo hizo una vez — reinterpretar mal un monto (ej. dividirlo por la cantidad
    de cuotas en vez de tomarlo tal cual). El texto extraído del PDF no tiene ese
    problema: cuando hay cupón y la diferencia es real, gana siempre el impreso.
    """
    printed = _extract_printed_amounts(extracted_text)
    if not printed:
        return transactions

    for txn in transactions:
        cupon = txn.get("cupon")
        if not cupon:
            continue
        real = printed.get(str(cupon))
        if real is None:
            continue

        amount = txn.get("amount")
        if amount is None:
            continue

        sign = -1 if amount < 0 else 1
        reported = Decimal(str(abs(amount)))
        if abs(reported - real) <= Decimal("0.01"):
            continue  # coincide con lo impreso, nada que corregir

        corrected = float(sign * real)
        print(
            f"[worker] cupón {cupon}: monto del LLM ({amount}) no coincide con el "
            f"impreso ({corrected}) — corregido y marcado para revisión: "
            f"{txn.get('description')!r}"
        )
        txn["amount"] = corrected
        if txn.get("installments"):
            txn["installments"]["amount_per"] = float(real)
        txn["confidence"] = min(float(txn.get("confidence", 1.0)), 0.5)

    return transactions
