"""Configure CORS on the S3 bucket to allow browser uploads from localhost and production."""

import sys
import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, ".")
from app.config import settings

CORS_RULES = [
    {
        "AllowedHeaders": ["*"],
        "AllowedMethods": ["PUT", "GET"],
        "AllowedOrigins": [
            "http://localhost:5173",
            "file://",
        ],
        "ExposeHeaders": ["ETag"],
        "MaxAgeSeconds": 3000,
    }
]


def main() -> None:
    s3 = boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )

    try:
        s3.put_bucket_cors(
            Bucket=settings.s3_bucket_name,
            CORSConfiguration={"CORSRules": CORS_RULES},
        )
        print(f"CORS configurado en bucket '{settings.s3_bucket_name}'")
        print(f"Origins permitidos: {[r for rule in CORS_RULES for r in rule['AllowedOrigins']]}")
    except ClientError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
