"""Validate that audio files exist for the target date (S3 or local)."""

from __future__ import annotations

import os
import sys
from datetime import date

from asr_system.config import Settings, get_settings
from services.batch.date_context import resolve_target_date

AUDIO_EXTENSIONS = (".wav", ".mp3", ".flac")
NO_RECORDINGS_EXIT_CODE = 42


def _count_s3_recordings(settings: Settings, target_date: date) -> int:
    import boto3

    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.batch_secrets.storage_access_key,
        aws_secret_access_key=settings.batch_secrets.storage_secret_key,
        endpoint_url=settings.s3.endpoint_url or None,
        region_name=settings.s3.region,
    )
    prefix = f"{settings.s3.prefix.rstrip('/')}/{target_date.isoformat()}/"
    pages = s3.get_paginator("list_objects_v2").paginate(Bucket=settings.s3.bucket, Prefix=prefix)
    return sum(
        1
        for page in pages
        for obj in page.get("Contents", [])
        if obj["Key"].endswith(AUDIO_EXTENSIONS)
    )


def _count_local_recordings(settings: Settings, target_date: date) -> int:
    day_dir = os.path.join(settings.storage.input_dir, target_date.isoformat())
    if not os.path.isdir(day_dir):
        return 0
    return len([filename for filename in os.listdir(day_dir) if filename.endswith(AUDIO_EXTENSIONS)])


def count_recordings(settings: Settings, target_date: date) -> int:
    if settings.s3.bucket:
        return _count_s3_recordings(settings, target_date)
    return _count_local_recordings(settings, target_date)


def main() -> int:
    target_date = resolve_target_date()
    settings = get_settings()
    recordings_count = count_recordings(settings, target_date)
    source = f"s3://{settings.s3.bucket}" if settings.s3.bucket else "local"
    print(f"validate [{source}]: {recordings_count} recordings for {target_date.isoformat()}")
    return 0 if recordings_count else NO_RECORDINGS_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
