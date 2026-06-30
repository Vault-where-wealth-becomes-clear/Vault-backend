def split_by_confidence(
    transactions: list[dict], threshold: float
) -> tuple[list[dict], list[dict]]:
    auto, review = [], []
    for txn in transactions:
        confidence = float(txn.get("confidence", 0))
        txn["needs_review"] = confidence < threshold
        (review if txn["needs_review"] else auto).append(txn)
    return auto, review
