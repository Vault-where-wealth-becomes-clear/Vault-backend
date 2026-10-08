"""El worker logueaba con print(): sin estructura, sin nivel y sin forma de
correlacionar las lineas de un mismo upload mas alla de lo que estuviera
interpolado en el string."""

import json

import structlog

from app.logging_config import configure_logging
from worker.processors import ledger_verifier


def _emitir_y_leer(capsys, **kwargs) -> dict:
    configure_logging()
    # El logger de un modulo anidado del pipeline, no uno creado en el test:
    # lo que se verifica es que la correlacion llegue hasta ahi.
    ledger_verifier.logger.warning("ledger_amount_corrected", **kwargs)
    return json.loads(capsys.readouterr().out.strip())


def test_worker_logs_are_parseable_json_with_a_level(capsys):
    linea = _emitir_y_leer(capsys, llm_amount=1500.0, printed_amount=1200.0)

    assert linea["event"] == "ledger_amount_corrected"
    assert linea["level"] == "warning"
    assert linea["llm_amount"] == 1500.0
    assert "timestamp" in linea


def test_a_bound_upload_id_reaches_logs_from_nested_modules(capsys):
    """La correlacion se ata una vez en el limite del job (worker/run.py) y
    tiene que aparecer en cada linea que emita ese upload, sin que ninguna
    funcion intermedia reciba el id por parametro."""
    structlog.contextvars.bind_contextvars(upload_id="abc-123")
    try:
        linea = _emitir_y_leer(capsys, llm_amount=1500.0)
    finally:
        structlog.contextvars.unbind_contextvars("upload_id")

    assert linea["upload_id"] == "abc-123"


def test_unbinding_stops_the_correlation_leaking_into_the_next_job(capsys):
    structlog.contextvars.bind_contextvars(upload_id="abc-123")
    structlog.contextvars.unbind_contextvars("upload_id")

    linea = _emitir_y_leer(capsys, llm_amount=1500.0)

    assert "upload_id" not in linea
