import structlog


def configure_logging() -> None:
    """Configura structlog para todo el proceso, sea la API o el worker.

    Vivia inline en `app/main.py`, asi que solo se aplicaba si algo importaba
    ese modulo. El worker standalone (`python -m worker.run`) nunca lo importa
    y por lo tanto escribia con la config por defecto de structlog en vez de
    JSON — justo el proceso cuyos logs mas falta hace poder parsear.

    `merge_contextvars` va primero: es lo que hace que el `upload_id` atado al
    contexto de un job aparezca en cada linea que emita ese job, sin tener que
    pasar un logger por parametro hasta el ultimo processor.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    )
