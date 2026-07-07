import re
from decimal import Decimal

_LEDGER_LINE_RE = re.compile(
    r"^\d{2}[/-]\d{2}(?:-\d{4})?\s+.*?(?P<amount>-?[0-9.]*[0-9],[0-9]{2})"
    r"\s*\$?\s*(?P<saldo>-?[0-9.]*[0-9],[0-9]{2})\s*$"
)


def _parse_ar_number(raw: str) -> Decimal:
    return Decimal(raw.replace(".", "").replace(",", "."))


def parse_ledger_lines(text: str) -> list[tuple[Decimal, Decimal]]:
    """
    Devuelve [(monto, saldo_resultante), ...] en el orden impreso, leyendo
    directo el texto de un extracto de cuenta (CA/CC) con formato de libro
    diario. El banco imprime, en cada línea de movimiento, el monto (con signo
    implícito por columna débito/crédito) y el saldo resultante — los dos
    últimos números de la línea, siempre en ese orden. No hace falta que nadie
    reinterprete esos números: son la cuenta que ya hizo el banco.
    """
    out = []
    for line in text.splitlines():
        m = _LEDGER_LINE_RE.match(line.strip())
        if not m:
            continue
        out.append((_parse_ar_number(m.group("amount")), _parse_ar_number(m.group("saldo"))))
    return out


def verify_and_correct_ledger(transactions: list[dict], extracted_text: str) -> list[dict]:
    """
    Corrige `amount` de movimientos de cuenta (CA/CC) contra el monto impreso
    en el extracto original. El LLM puede confundir débito/crédito por el
    significado de la descripción (ej. "COMPRA VENTA MON.EXTRANJERA" leído como
    gasto cuando el banco lo acreditó); el texto extraído no tiene ese
    problema. De paso, guarda el saldo impreso de cada línea en
    `txn["_printed_saldo"]` — lo usa `reconciliation_gap` después.

    Alineación posicional: solo corrige si la cantidad de líneas de movimiento
    detectadas en el texto coincide exactamente con la cantidad de
    transacciones que devolvió el LLM para todo el documento — si no coincide
    (el LLM agregó, partió o se comió una línea), no se toca nada para no
    alinear mal.
    """
    lines = parse_ledger_lines(extracted_text)
    if not lines or len(lines) != len(transactions):
        return transactions

    for txn, (printed_amount, saldo) in zip(transactions, lines):
        txn["_printed_saldo"] = float(saldo)

        amount = txn.get("amount")
        if amount is None:
            continue
        reported = Decimal(str(amount))
        if abs(reported - printed_amount) <= Decimal("0.01"):
            continue
        print(
            f"[worker] ledger: monto del LLM ({amount}) no coincide con el impreso "
            f"({printed_amount}) — corregido y marcado para revisión: "
            f"{txn.get('description')!r} {txn.get('date')!r}"
        )
        txn["amount"] = float(printed_amount)
        txn["confidence"] = min(float(txn.get("confidence", 1.0)), 0.5)

    return transactions


def reconciliation_gap(sub_txns: list[dict], opening_balance: Decimal) -> Decimal | None:
    """
    Créditos - débitos + saldo anterior, comparado contra el último saldo
    impreso que quedó alineado a este sub-período. `None` si ninguna
    transacción del sub-período tiene saldo impreso asociado (no hubo
    alineación posicional — ver `verify_and_correct_ledger`), porque en ese
    caso no hay nada confiable contra qué comparar.
    """
    last_saldo = last_printed_saldo(sub_txns)
    if last_saldo is None:
        return None

    net = sum((Decimal(str(t.get("amount", 0))) for t in sub_txns), Decimal("0"))
    return (opening_balance + net) - last_saldo


def last_printed_saldo(sub_txns: list[dict]) -> Decimal | None:
    """
    Saldo impreso de la última transacción del sub-período (en orden real,
    no por fecha). Es el saldo de cierre real de ese mes según el banco — se
    usa para encadenar el saldo inicial del mes siguiente en un PDF
    consolidado que trae varios períodos juntos, en vez de asumir 0.
    """
    for t in reversed(sub_txns):
        if "_printed_saldo" in t:
            return Decimal(str(t["_printed_saldo"]))
    return None
