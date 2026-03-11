from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    provider: str = Field(default="whisper", alias="BATCH_ASR_PROVIDER")
    model_name: str = Field(default="whisper-large-v3-turbo", alias="BATCH_ASR_MODEL")


class EmotionSettings(BaseEnvSettings):
    provider: str = Field(default="rubert", alias="BATCH_EMOTION_PROVIDER")
    model_name: str = Field(default="cointegrated/rubert-tiny2", alias="BATCH_EMOTION_MODEL")


class AirflowSettings(BaseEnvSettings):
    schedule: str = Field(default="0 0 * * *", alias="BATCH_AIRFLOW_SCHEDULE")
    sla_hour_msk: int = Field(default=8, alias="BATCH_AIRFLOW_SLA_HOUR_MSK")


class ApiSettings(BaseEnvSettings):
    host: str = Field(default="0.0.0.0", alias="ONLINE_API_HOST")
    port: int = Field(default=8080, alias="ONLINE_API_PORT")


class BatchSecretsSettings(BaseEnvSettings):
    storage_access_key: str = Field(default="", alias="BATCH_STORAGE_ACCESS_KEY")
    storage_secret_key: str = Field(default="", alias="BATCH_STORAGE_SECRET_KEY")


class OnlineSecretsSettings(BaseEnvSettings):
    api_token: str = Field(default="", alias="ONLINE_API_TOKEN")


class Settings(BaseSettings):
    app: AppSettings
    storage: StorageSettings
    db: DatabaseSettings
    asr: AsrSettings
    emotion: EmotionSettings
    airflow: AirflowSettings
    api: ApiSettings
    batch_secrets: BatchSecretsSettings
    online_secrets: OnlineSecretsSettings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app=AppSettings(),
        storage=StorageSettings(),
        db=DatabaseSettings(),
        asr=AsrSettings(),
        emotion=EmotionSettings(),
        airflow=AirflowSettings(),
        api=ApiSettings(),
        batch_secrets=BatchSecretsSettings(),
        online_secrets=OnlineSecretsSettings(),
    )
