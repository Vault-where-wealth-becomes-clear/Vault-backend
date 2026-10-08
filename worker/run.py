"""Worker local de desarrollo: long-polling de SQS + procesamiento de uploads.

No es el artefacto de deploy de AWS Lambda (ese vive en `lambda/` y se empaqueta
por separado). Este script corre en un proceso aparte durante el desarrollo
local para que el flujo upload -> Claude -> dashboard sea testeable de punta
a punta sin desplegar nada en AWS todavía.

Uso: desde Vault-backend/, con el venv activado y .env cargado:
    python -m worker.run

`poll_loop()` tambien se reusa para correr el worker in-process dentro del
mismo servicio que la API (ver app/main.py, gateado por RUN_WORKER_INLINE) en
deploys donde no hay forma de levantar un segundo proceso/servicio gratis.
"""

import asyncio
import json
import time

import boto3
import structlog

from app.config import settings
from app.logging_config import configure_logging
from worker.processing import process_upload

logger = structlog.get_logger()


async def poll_loop() -> None:
    if not settings.sqs_queue_url:
        raise SystemExit("SQS_QUEUE_URL no esta configurado en .env")

    configure_logging()
    loop = asyncio.get_running_loop()
    sqs = boto3.client(
        "sqs",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        endpoint_url=settings.aws_endpoint_url or None,
    )

    logger.info("worker_listening", queue_url=settings.sqs_queue_url)
    while True:
        response = await loop.run_in_executor(
            None,
            lambda: sqs.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,
            ),
        )
        for message in response.get("Messages", []):
            body = json.loads(message["Body"])
            upload_id = body.get("upload_id")
            # El limite del job es el mensaje, asi que la correlacion se ata
            # aca: a partir de este punto toda linea que emita el pipeline
            # —processing, processors, cliente del LLM— sale con su upload_id,
            # sin pasar un logger por parametro hasta el ultimo helper.
            structlog.contextvars.bind_contextvars(upload_id=upload_id)
            logger.info("upload_received")
            # Reloj monotonico: `duration_seconds` mide tiempo transcurrido y
            # no puede saltar si el reloj del host se ajusta.
            started = time.monotonic()
            try:
                await process_upload(body)
                await loop.run_in_executor(
                    None,
                    lambda: sqs.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    ),
                )
                logger.info(
                    "upload_processed",
                    duration_seconds=round(time.monotonic() - started, 3),
                )
            except Exception as exc:
                logger.error(
                    "upload_failed",
                    duration_seconds=round(time.monotonic() - started, 3),
                    error=str(exc),
                    exc_info=True,
                )
            finally:
                structlog.contextvars.unbind_contextvars("upload_id")


if __name__ == "__main__":
    asyncio.run(poll_loop())
