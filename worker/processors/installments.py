from decimal import Decimal


def _parse_installments_field(info) -> dict | None:
    """Normaliza installments a dict independientemente de si Claude devolvió
    un string ('3/12') o un objeto ({'current': 3, 'total': 12, ...})."""
    if not info:
        return None
    if isinstance(info, str):
        parts = info.split("/")
        if len(parts) == 2:
            try:
                return {"current": int(parts[0].strip()), "total": int(parts[1].strip())}
            except ValueError:
                return None
        return None
    if isinstance(info, dict):
        return info
    return None


def extract_installments(transactions: list[dict]) -> list[dict]:
    results = []
    for txn in transactions:
        info = _parse_installments_field(txn.get("installments"))
        if not info:
            continue
        current = (
            info.get("current")
            or info.get("current_installment")
            or info.get("numero")
            or info.get("cuota_actual")
        )
        total = info.get("total") or info.get("total_installments") or info.get("total_cuotas")
        amount_per = (
            info.get("amount_per")
            or info.get("amount_per_installment")
            or info.get("monto_cuota")
            or info.get("monto")
        )
        if not (current and total and amount_per):
            continue
        results.append(
            {
                "description": txn["description"],
                "current_installment": current,
                "total_installments": total,
                "amount_per_installment": Decimal(str(amount_per)),
                "currency": txn.get("currency", "ARS"),
                "_txn_ref": txn,
            }
        )
    return results
