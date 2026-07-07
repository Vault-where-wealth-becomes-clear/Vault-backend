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
import traceback

import boto3

from app.config import settings
from worker.processing import process_upload


async def poll_loop() -> None:
    if not settings.sqs_queue_url:
        raise SystemExit("SQS_QUEUE_URL no esta configurado en .env")

    loop = asyncio.get_running_loop()
    sqs = boto3.client(
        "sqs",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        endpoint_url=settings.aws_endpoint_url or None,
    )

    print(f"[worker] escuchando {settings.sqs_queue_url}")
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
            print(f"[worker] procesando upload {upload_id}")
            try:
                await process_upload(body)
                await loop.run_in_executor(
                    None,
                    lambda: sqs.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=message["ReceiptHandle"],
                    ),
                )
                print(f"[worker] upload {upload_id} terminado")
            except Exception:
                traceback.print_exc()
                print(f"[worker] upload {upload_id} fallo, queda en la cola para reintento")


if __name__ == "__main__":
    asyncio.run(poll_loop())
