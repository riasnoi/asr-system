"""Validate that audio files exist for the target date (S3 or local)."""

import os
import sys
from datetime import date

from asr_system.config import get_settings

raw = os.environ.get("AIRFLOW_CTX_LOGICAL_DATE", "")
d = raw[:10] if raw else date.today().isoformat()

settings = get_settings()
bucket = settings.s3.bucket
exts = (".wav", ".mp3", ".flac")
n = 0

if bucket:
    import boto3

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.batch_secrets.storage_access_key,
        aws_secret_access_key=settings.batch_secrets.storage_secret_key,
        endpoint_url=settings.s3.endpoint_url or None,
        region_name=settings.s3.region,
    )
    prefix = settings.s3.prefix.rstrip("/") + "/" + d + "/"
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix)
    n = sum(
        1
        for page in pages
        for obj in page.get("Contents", [])
        if any(obj["Key"].endswith(e) for e in exts)
    )
else:
    inp = settings.storage.input_dir
    day = os.path.join(inp, d)
    n = len([f for f in os.listdir(day) if f.endswith(exts)]) if os.path.isdir(day) else 0

src = f"s3://{bucket}" if bucket else "local"
print(f"validate [{src}]: {n} recordings for {d}")
sys.exit(0 if n else 1)
