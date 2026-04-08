"""Verify that call_scores.jsonl was uploaded to S3 for the target date."""

import os
import sys
from datetime import date

import boto3

from asr_system.config import get_settings

raw = os.environ.get("AIRFLOW_CTX_LOGICAL_DATE", "")
d = raw[:10] if raw else date.today().isoformat()

settings = get_settings()
key = f"results/{d}/call_scores.jsonl"

client = boto3.client(
    "s3",
    aws_access_key_id=settings.batch_secrets.storage_access_key,
    aws_secret_access_key=settings.batch_secrets.storage_secret_key,
    endpoint_url=settings.s3.endpoint_url or None,
    region_name=settings.s3.region,
)

try:
    size = client.head_object(Bucket=settings.s3.bucket, Key=key)["ContentLength"]
    ok = size > 0
except Exception as exc:
    print(f"error: {exc}")
    ok = False

print(f"verify s3://{settings.s3.bucket}/{key} ok={ok}")
sys.exit(0 if ok else 1)
