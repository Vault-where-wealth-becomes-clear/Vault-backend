from decimal import Decimal


def extract_installments(transactions: list[dict]) -> list[dict]:
    results = []
    for txn in transactions:
        info = txn.get("installments")
        if not info:
            continue
        results.append(
            {
                "description": txn["description"],
                "current_installment": info["current"],
                "total_installments": info["total"],
                "amount_per_installment": Decimal(str(info["amount_per"])),
                "currency": txn.get("currency", "ARS"),
                "_txn_ref": txn,
            }
        )
    return results
