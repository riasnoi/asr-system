from unittest.mock import MagicMock, patch

import pytest

from asr_system.infrastructure.secrets.vault_provider import VaultSecretsProvider, VaultSettings


@pytest.fixture()
def vault_settings() -> VaultSettings:
    return VaultSettings(
        VAULT_ENABLED=True,
        VAULT_ADDR="http://vault-test:8200",
        VAULT_AUTH_METHOD="approle",
        VAULT_TOKEN="",
        VAULT_ROLE_ID="test-role",
        VAULT_SECRET_ID="test-secret",
        VAULT_MOUNT_POINT="secret",
        VAULT_BASE_PATH="asr-system",
    )


@pytest.fixture()
def vault_settings_token() -> VaultSettings:
    return VaultSettings(
        VAULT_ENABLED=True,
        VAULT_ADDR="http://vault-test:8200",
        VAULT_AUTH_METHOD="token",
        VAULT_TOKEN="s.test-token",
        VAULT_ROLE_ID="",
        VAULT_SECRET_ID="",
        VAULT_MOUNT_POINT="secret",
        VAULT_BASE_PATH="asr-system",
    )


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_approle_authentication(mock_client_cls: MagicMock, vault_settings: VaultSettings) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.auth.approle.login.return_value = {"auth": {"client_token": "s.approle-tok"}}
    mock_client.is_authenticated.return_value = True

    provider = VaultSecretsProvider(vault_settings)

    mock_client.auth.approle.login.assert_called_once_with(
        role_id="test-role",
        secret_id="test-secret",
    )
    assert mock_client.token == "s.approle-tok"
    assert provider is not None


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_token_authentication(
    mock_client_cls: MagicMock, vault_settings_token: VaultSettings
) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.is_authenticated.return_value = True

    provider = VaultSecretsProvider(vault_settings_token)

    mock_client.auth.approle.login.assert_not_called()
    assert mock_client.token == "s.test-token"
    assert provider is not None


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_authentication_failure_raises(
    mock_client_cls: MagicMock, vault_settings: VaultSettings
) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.auth.approle.login.return_value = {"auth": {"client_token": "s.bad"}}
    mock_client.is_authenticated.return_value = False

    with pytest.raises(RuntimeError, match="Vault authentication failed"):
        VaultSecretsProvider(vault_settings)


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_unsupported_auth_method_raises(mock_client_cls: MagicMock) -> None:
    mock_client_cls.return_value = MagicMock()
    settings = VaultSettings(
        VAULT_ENABLED=True,
        VAULT_ADDR="http://vault-test:8200",
        VAULT_AUTH_METHOD="ldap",
        VAULT_TOKEN="",
        VAULT_ROLE_ID="",
        VAULT_SECRET_ID="",
        VAULT_MOUNT_POINT="secret",
        VAULT_BASE_PATH="asr-system",
    )

    with pytest.raises(ValueError, match="Unsupported VAULT_AUTH_METHOD"):
        VaultSecretsProvider(settings)


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_get_secret_reads_kv_v2(mock_client_cls: MagicMock, vault_settings: VaultSettings) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.auth.approle.login.return_value = {"auth": {"client_token": "s.tok"}}
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"ONLINE_API_TOKEN": "secret-123"}}
    }

    provider = VaultSecretsProvider(vault_settings)
    result = provider.get_secret("online")

    mock_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
        path="asr-system/online",
        mount_point="secret",
    )
    assert result == {"ONLINE_API_TOKEN": "secret-123"}


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_get_secret_caches_result(
    mock_client_cls: MagicMock, vault_settings: VaultSettings
) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.auth.approle.login.return_value = {"auth": {"client_token": "s.tok"}}
    mock_client.is_authenticated.return_value = True
    mock_client.secrets.kv.v2.read_secret_version.return_value = {
        "data": {"data": {"DB_DSN": "postgres://..."}}
    }

    provider = VaultSecretsProvider(vault_settings)
    first = provider.get_secret("app")
    second = provider.get_secret("app")

    assert first is second
    assert mock_client.secrets.kv.v2.read_secret_version.call_count == 1


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_load_all_collects_scopes(
    mock_client_cls: MagicMock, vault_settings: VaultSettings
) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.auth.approle.login.return_value = {"auth": {"client_token": "s.tok"}}
    mock_client.is_authenticated.return_value = True

    secrets_by_path = {
        "asr-system/app": {"DB_DSN": "postgres://prod"},
        "asr-system/batch": {"BATCH_STORAGE_ACCESS_KEY": "ak", "BATCH_STORAGE_SECRET_KEY": "sk"},
        "asr-system/online": {"ONLINE_API_TOKEN": "tok-xyz"},
    }

    def read_secret(path: str, mount_point: str) -> dict:
        return {"data": {"data": secrets_by_path[path]}}

    mock_client.secrets.kv.v2.read_secret_version.side_effect = read_secret

    provider = VaultSecretsProvider(vault_settings)
    result = provider.load_all()

    assert result["app"]["DB_DSN"] == "postgres://prod"
    assert result["batch"]["BATCH_STORAGE_ACCESS_KEY"] == "ak"
    assert result["online"]["ONLINE_API_TOKEN"] == "tok-xyz"


@patch("asr_system.infrastructure.secrets.vault_provider.hvac.Client")
def test_load_all_skips_failed_scopes(
    mock_client_cls: MagicMock, vault_settings: VaultSettings
) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.auth.approle.login.return_value = {"auth": {"client_token": "s.tok"}}
    mock_client.is_authenticated.return_value = True

    def read_secret(path: str, mount_point: str) -> dict:
        if "batch" in path:
            raise Exception("Vault unavailable for batch")
        return {"data": {"data": {"key": "val"}}}

    mock_client.secrets.kv.v2.read_secret_version.side_effect = read_secret

    provider = VaultSecretsProvider(vault_settings)
    result = provider.load_all()

    assert "app" in result
    assert "online" in result
    assert "batch" not in result
