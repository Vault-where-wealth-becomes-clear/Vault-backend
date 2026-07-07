import json

import boto3

from app.config import settings


class SQSClient:
    def __init__(self) -> None:
        self.client = boto3.client(
            "sqs",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
            endpoint_url=settings.aws_endpoint_url or None,
        )
        self.queue_url = settings.sqs_queue_url

    def send_message(self, body: dict) -> str:
        response = self.client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(body),
        )
        return response["MessageId"]


def get_sqs() -> SQSClient:
    return SQSClient()
