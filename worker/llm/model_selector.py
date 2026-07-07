from app.config import settings
from worker.processors.amount_verifier import _extract_printed_amounts
from worker.processors.ledger_verifier import parse_ledger_lines


def count_movements(text: str) -> int:
    """
    Cantidad real de movimientos en el extracto, contada de forma
    determinística (sin LLM) — cupones de tarjeta o líneas de libro diario,
    lo que aplique según el formato del documento. Se usa para decidir qué
    modelo llamar, no para extraer datos.
    """
    return max(len(_extract_printed_amounts(text)), len(parse_ledger_lines(text)))


def select_model(text: str) -> str:
    """
    Extractos grandes (muchos movimientos, típicamente PDFs consolidados de
    varios meses) necesitan un modelo más grande — confirmado con
    claude-haiku-4-5: se corta después del primer período reconciliado en
    documentos así, sin importar el límite de tokens. Para extractos chicos
    (la mayoría de las cargas) el modelo default es suficiente y más barato.
    """
    if count_movements(text) > settings.llm_large_doc_threshold:
        return settings.llm_model_large
    return settings.llm_model
