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
    input_dir: str = Field(default="./data/input", alias="STORAGE_INPUT_DIR")
    output_dir: str = Field(default="./data/output", alias="STORAGE_OUTPUT_DIR")


class DatabaseSettings(BaseEnvSettings):
    dsn: str = Field(default="sqlite:///./data/asr.db", alias="DB_DSN")


class AsrSettings(BaseEnvSettings):
    provider: str = Field(default="whisper", alias="ASR_PROVIDER")
    model_name: str = Field(default="whisper-large-v3-turbo", alias="ASR_MODEL")


class EmotionSettings(BaseEnvSettings):
    provider: str = Field(default="rubert", alias="EMOTION_PROVIDER")
    model_name: str = Field(default="cointegrated/rubert-tiny2", alias="EMOTION_MODEL")


class AirflowSettings(BaseEnvSettings):
    schedule: str = Field(default="0 0 * * *", alias="AIRFLOW_SCHEDULE")
    sla_hour_msk: int = Field(default=8, alias="AIRFLOW_SLA_HOUR_MSK")


class ApiSettings(BaseEnvSettings):
    host: str = Field(default="0.0.0.0", alias="ONLINE_API_HOST")
    port: int = Field(default=8080, alias="ONLINE_API_PORT")


class Settings(BaseSettings):
    app: AppSettings
    storage: StorageSettings
    db: DatabaseSettings
    asr: AsrSettings
    emotion: EmotionSettings
    airflow: AirflowSettings
    api: ApiSettings


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
    )
