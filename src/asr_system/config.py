from __future__ import annotations

import logging
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class BaseEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppSettings(BaseEnvSettings):
    env: str = Field(default="dev", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="APP_LOG_LEVEL")


class StorageSettings(BaseEnvSettings):
    input_dir: str = Field(default="./data/input", alias="BATCH_INPUT_DIR")
    output_dir: str = Field(default="./data/output", alias="BATCH_OUTPUT_DIR")


class DatabaseSettings(BaseEnvSettings):
    dsn: str = Field(default="sqlite:///./data/asr.db", alias="DB_DSN")


class AsrSettings(BaseEnvSettings):
    provider: str = Field(default="mock", alias="BATCH_ASR_PROVIDER")
    model_name: str = Field(default="whisper-large-v3-turbo", alias="BATCH_ASR_MODEL")
    remote_url: str = Field(default="", alias="BATCH_ASR_REMOTE_URL")


class EmotionSettings(BaseEnvSettings):
    provider: str = Field(default="rule", alias="BATCH_EMOTION_PROVIDER")
    model_name: str = Field(default="rubert-tiny2", alias="BATCH_EMOTION_MODEL")
    remote_url: str = Field(default="", alias="BATCH_EMOTION_REMOTE_URL")


class AirflowSettings(BaseEnvSettings):
    schedule: str = Field(default="0 0 * * *", alias="BATCH_AIRFLOW_SCHEDULE")
    sla_hour_msk: int = Field(default=8, alias="BATCH_AIRFLOW_SLA_HOUR_MSK")


class ApiSettings(BaseEnvSettings):
    host: str = Field(default="0.0.0.0", alias="ONLINE_API_HOST")
    port: int = Field(default=8080, alias="ONLINE_API_PORT")


class S3Settings(BaseEnvSettings):
    bucket: str = Field(default="", alias="BATCH_S3_BUCKET")
    endpoint_url: str = Field(default="", alias="BATCH_S3_ENDPOINT_URL")
    prefix: str = Field(default="recordings", alias="BATCH_S3_PREFIX")
    region: str = Field(default="us-east-1", alias="BATCH_S3_REGION")


class BatchSecretsSettings(BaseEnvSettings):
    storage_access_key: str = Field(default="", alias="BATCH_STORAGE_ACCESS_KEY")
    storage_secret_key: str = Field(default="", alias="BATCH_STORAGE_SECRET_KEY")


class OnlineSecretsSettings(BaseEnvSettings):
    api_token: str = Field(default="", alias="ONLINE_API_TOKEN")


class Settings(BaseSettings):
    app: AppSettings
    storage: StorageSettings
    s3: S3Settings
    db: DatabaseSettings
    asr: AsrSettings
    emotion: EmotionSettings
    airflow: AirflowSettings
    api: ApiSettings
    batch_secrets: BatchSecretsSettings
    online_secrets: OnlineSecretsSettings


def _apply_vault_overrides() -> dict[str, dict[str, str]]:
    """Load secrets from Vault if VAULT_ENABLED=true, otherwise return empty."""
    from asr_system.infrastructure.secrets.vault_provider import VaultSettings

    vault_cfg = VaultSettings()
    if not vault_cfg.enabled:
        return {}

    from asr_system.infrastructure.secrets.vault_provider import VaultSecretsProvider

    logger.info("Vault enabled, loading secrets from %s", vault_cfg.addr)
    try:
        provider = VaultSecretsProvider(vault_cfg)
        return provider.load_all()
    except Exception:
        logger.exception("Failed to connect to Vault — starting with default/env secrets")
        return {}


def _pick(src: dict[str, str], prefix: str) -> dict[str, str]:
    """Extract keys starting with *prefix* from *src* (case-insensitive)."""
    prefix_lower = prefix.lower()
    return {k: v for k, v in src.items() if k.lower().startswith(prefix_lower)}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    overrides = _apply_vault_overrides()

    batch_kw = overrides.get("batch", {})
    online_kw = overrides.get("online", {})
    app_kw = overrides.get("app", {})

    return Settings(
        app=AppSettings(),
        storage=StorageSettings(),
        s3=S3Settings(**_pick(batch_kw, "BATCH_S3_")),
        db=DatabaseSettings(**_pick(app_kw, "DB_")),
        asr=AsrSettings(**_pick(batch_kw, "BATCH_ASR_")),
        emotion=EmotionSettings(**_pick(batch_kw, "BATCH_EMOTION_")),
        airflow=AirflowSettings(),
        api=ApiSettings(),
        batch_secrets=BatchSecretsSettings(**_pick(batch_kw, "BATCH_STORAGE_")),
        online_secrets=OnlineSecretsSettings(**_pick(online_kw, "ONLINE_")),
    )
