from decimal import Decimal


def apply_mep_conversion(transactions: list[dict], mep_rate: Decimal) -> list[dict]:
    for txn in transactions:
        amount = Decimal(str(txn["amount"]))
        if txn.get("currency", "ARS") == "ARS":
            txn["amount_ars"] = amount
            txn["amount_usd"] = (amount / mep_rate).quantize(Decimal("0.0001"))
        else:
            txn["amount_usd"] = amount
            txn["amount_ars"] = (amount * mep_rate).quantize(Decimal("0.01"))
    return transactions
