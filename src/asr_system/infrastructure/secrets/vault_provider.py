from __future__ import annotations

import logging
from typing import Any

import hvac
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class VaultSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(default=False, alias="VAULT_ENABLED")
    addr: str = Field(default="http://127.0.0.1:8200", alias="VAULT_ADDR")
    auth_method: str = Field(default="approle", alias="VAULT_AUTH_METHOD")
    token: str = Field(default="", alias="VAULT_TOKEN")
    role_id: str = Field(default="", alias="VAULT_ROLE_ID")
    secret_id: str = Field(default="", alias="VAULT_SECRET_ID")
    mount_point: str = Field(default="secret", alias="VAULT_MOUNT_POINT")
    base_path: str = Field(default="asr-system", alias="VAULT_BASE_PATH")


class VaultSecretsProvider:
    """Fetches application secrets from HashiCorp Vault KV v2."""

    def __init__(self, settings: VaultSettings) -> None:
        self._settings = settings
        self._cache: dict[str, dict[str, str]] = {}
        self._client = hvac.Client(url=settings.addr)
        self._authenticate()

    def _authenticate(self) -> None:
        if self._settings.auth_method == "token":
            self._client.token = self._settings.token
        elif self._settings.auth_method == "approle":
            resp = self._client.auth.approle.login(
                role_id=self._settings.role_id,
                secret_id=self._settings.secret_id,
            )
            self._client.token = resp["auth"]["client_token"]
        else:
            raise ValueError(f"Unsupported VAULT_AUTH_METHOD: {self._settings.auth_method}")

        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

        logger.info("Vault authentication successful (method=%s)", self._settings.auth_method)

    def get_secret(self, path: str) -> dict[str, str]:
        """Read all key-value pairs from a KV v2 path (with caching)."""
        full_path = f"{self._settings.base_path}/{path}"
        if full_path in self._cache:
            return self._cache[full_path]

        response: Any = self._client.secrets.kv.v2.read_secret_version(
            path=full_path,
            mount_point=self._settings.mount_point,
        )
        data: dict[str, str] = response["data"]["data"]
        self._cache[full_path] = data
        logger.info("Loaded secrets from Vault path=%s/%s", self._settings.mount_point, full_path)
        return data

    def load_all(self) -> dict[str, dict[str, str]]:
        """Load all application secrets grouped by scope.

        Returns a dict like::

            {
                "app":    {"DB_DSN": "..."},
                "batch":  {"BATCH_STORAGE_ACCESS_KEY": "...", ...},
                "online": {"ONLINE_API_TOKEN": "..."},
            }
        """
        scopes = ("app", "batch", "online")
        result: dict[str, dict[str, str]] = {}
        for scope in scopes:
            try:
                result[scope] = self.get_secret(scope)
            except Exception:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to load Vault scope '%s', skipping", scope, exc_info=True)
        return result
