"""Adapter factory: selects concrete implementations based on Settings."""

from __future__ import annotations

import logging

from asr_system.config import Settings
from asr_system.domain.ports import ASRPort, EmotionPort, IngestPort, SpeakerAttributionPort

logger = logging.getLogger(__name__)


def create_asr_adapter(settings: Settings) -> ASRPort:
    provider = settings.asr.provider
    if provider == "mock":
        from asr_system.infrastructure.asr.mock_asr import MockAsrAdapter

        return MockAsrAdapter()

    if provider == "remote":
        from asr_system.infrastructure.asr.triton_asr import TritonAsrAdapter

        return TritonAsrAdapter(url=settings.asr.remote_url, model=settings.asr.model_name)

    if provider == "whisper":
        try:
            from asr_system.infrastructure.asr.whisper_asr import WhisperAsrAdapter

            return WhisperAsrAdapter(model_name=settings.asr.model_name)
        except ImportError:
            logger.warning("whisper adapter not available, falling back to mock")
            from asr_system.infrastructure.asr.mock_asr import MockAsrAdapter

            return MockAsrAdapter()

    raise ValueError(f"Unknown ASR provider: {provider}")


def create_emotion_adapter(settings: Settings) -> EmotionPort:
    provider = settings.emotion.provider
    if provider == "rule":
        from asr_system.infrastructure.emotion.rule_based import RuleBasedEmotionAdapter

        return RuleBasedEmotionAdapter()

    if provider == "remote":
        from asr_system.infrastructure.emotion.triton_emotion import TritonEmotionAdapter

        return TritonEmotionAdapter(
            url=settings.emotion.remote_url, model=settings.emotion.model_name
        )

    if provider == "rubert":
        try:
            from asr_system.infrastructure.emotion.rubert_emotion import RuBertEmotionAdapter

            return RuBertEmotionAdapter(model_name=settings.emotion.model_name)
        except ImportError:
            logger.warning("rubert adapter not available, falling back to rule-based")
            from asr_system.infrastructure.emotion.rule_based import RuleBasedEmotionAdapter

            return RuleBasedEmotionAdapter()

    raise ValueError(f"Unknown emotion provider: {provider}")


def create_speaker_adapter(_settings: Settings) -> SpeakerAttributionPort:
    from asr_system.infrastructure.speaker.rule_speaker import AlternatingSpeakerAttribution

    return AlternatingSpeakerAttribution()


def create_ingest_adapter(settings: Settings) -> IngestPort:
    bucket = settings.s3.bucket
    if bucket:
        from asr_system.infrastructure.ingest.s3 import S3Ingest

        return S3Ingest(
            bucket=bucket,
            access_key=settings.batch_secrets.storage_access_key,
            secret_key=settings.batch_secrets.storage_secret_key,
            local_input_dir=settings.storage.input_dir,
            prefix=settings.s3.prefix,
            endpoint_url=settings.s3.endpoint_url,
            region=settings.s3.region,
        )

    from asr_system.infrastructure.ingest.local_fs import LocalFsIngest

    return LocalFsIngest(settings.storage.input_dir)
