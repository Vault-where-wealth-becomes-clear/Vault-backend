"""Inicializa recursos de LocalStack para desarrollo local.

Crea el bucket S3, configura CORS, y crea las colas SQS.
Usa la configuración del .env (AWS_ENDPOINT_URL debe apuntar a LocalStack).

Uso: desde Vault-backend/
    python -m scripts.setup_localstack
"""

import sys
import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, ".")
from app.config import settings

CORS_RULES = [
    {
        "AllowedOrigins": ["http://localhost:5173", "http://localhost:3000"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000,
    }
]


def make_s3():
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        endpoint_url=settings.aws_endpoint_url or None,
    )


def make_sqs():
    return boto3.client(
        "sqs",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
        endpoint_url=settings.aws_endpoint_url or None,
    )


def setup_s3(s3) -> None:
    try:
        s3.create_bucket(Bucket=settings.s3_bucket_name)
        print(f"[s3] bucket '{settings.s3_bucket_name}' creado")
    except ClientError as e:
        if e.response["Error"]["Code"] == "BucketAlreadyOwnedByYou":
            print(f"[s3] bucket '{settings.s3_bucket_name}' ya existía")
        else:
            raise

    s3.put_bucket_cors(
        Bucket=settings.s3_bucket_name,
        CORSConfiguration={"CORSRules": CORS_RULES},
    )
    print(f"[s3] CORS configurado en '{settings.s3_bucket_name}'")


def setup_sqs(sqs) -> None:
    for queue_name in ["vault-processing", "vault-processing-dlq"]:
        try:
            r = sqs.create_queue(QueueName=queue_name)
            print(f"[sqs] cola creada: {r['QueueUrl']}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "QueueAlreadyExists":
                print(f"[sqs] cola '{queue_name}' ya existía")
            else:
                raise


def main() -> None:
    if not settings.aws_endpoint_url:
        print("ERROR: AWS_ENDPOINT_URL no está seteado. Setealo a http://localhost:4566")
        sys.exit(1)

    print(f"Conectando a LocalStack en {settings.aws_endpoint_url}...")
    setup_s3(make_s3())
    setup_sqs(make_sqs())
    print("Listo.")


if __name__ == "__main__":
    main()
