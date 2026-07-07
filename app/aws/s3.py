import boto3
from botocore.config import Config

from app.config import settings


class S3Client:
    def __init__(self) -> None:
        s3_config = Config(s3={"addressing_style": "path"}) if settings.aws_endpoint_url else None
        self.client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            endpoint_url=settings.aws_endpoint_url or None,
            config=s3_config,
        )
        self.bucket = settings.s3_bucket_name

    async def generate_presigned_url(
        self, key: str, content_type: str, expires_in: int = 300
    ) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires_in,
        )

    async def generate_presigned_get_url(self, key: str, expires_in: int = 900) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def download_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    async def delete_object(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    async def delete_prefix(self, prefix: str) -> None:
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            self.client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )


def get_s3() -> S3Client:
    return S3Client()
