# Secrets and Environment Management

## Principles

- No secrets in repository history.
- Local development uses `.env` from `.env.example` (`VAULT_ENABLED=false`).
- Production uses HashiCorp Vault via `VAULT_ENABLED=true`.
- CI/CD uses `hashicorp/vault-action` to fetch secrets at workflow runtime.
- Bootstrap Vault credentials are delivered to the server automatically by the deploy workflow.

## Scope separation

- Batch scope variables use `BATCH_*` prefix.
- Online scope variables use `ONLINE_*` prefix.
- Shared infrastructure variables keep explicit shared names (`DB_DSN`, etc.).

## Vault architecture

### KV v2 secret paths

```
secret/data/asr-system/
  app/           # DB_DSN
  batch/         # BATCH_ASR_PROVIDER, BATCH_ASR_MODEL, BATCH_ASR_REMOTE_URL,
                 # BATCH_EMOTION_PROVIDER, BATCH_EMOTION_MODEL, BATCH_EMOTION_REMOTE_URL,
                 # BATCH_STORAGE_ACCESS_KEY, BATCH_STORAGE_SECRET_KEY
  online/        # ONLINE_API_TOKEN
  airflow/       # POSTGRES_USER, POSTGRES_PASSWORD (Airflow DB)
  registry/      # GHCR_USERNAME, GHCR_TOKEN
```

### Authentication

Services authenticate to Vault using **AppRole** (`VAULT_ROLE_ID` + `VAULT_SECRET_ID`).
Token auth is available as a fallback for development.

### How secrets reach the application

1. `deploy.yml` reads `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID` from GitHub Secrets.
2. The deploy script generates `.env` on the server with only bootstrap credentials (no application secrets).
3. Docker containers start and the Python config layer (`config.py` + `VaultSecretsProvider`) fetches application secrets from Vault at process startup.
4. Airflow uses its native Vault Secrets Backend (`airflow-providers-hashicorp`) for connections and variables.

### Vault policies (recommended)

Create separate policies per service scope:

```hcl
# policy: asr-online
path "secret/data/asr-system/app" { capabilities = ["read"] }
path "secret/data/asr-system/online" { capabilities = ["read"] }

# policy: asr-batch
path "secret/data/asr-system/app" { capabilities = ["read"] }
path "secret/data/asr-system/batch" { capabilities = ["read"] }

# policy: asr-deploy (CI/CD)
path "secret/data/asr-system/registry" { capabilities = ["read"] }
```

## Required GitHub Secrets

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `REMOTE_APP_DIR`
- `GHCR_PAT` — Personal Access Token with `read:packages` scope (for K8s image pull)

## Local setup

```bash
cp .env.example .env
```

With `VAULT_ENABLED=false` (default), set values directly in `.env`:
- `BATCH_STORAGE_ACCESS_KEY`
- `BATCH_STORAGE_SECRET_KEY`
- `ONLINE_API_TOKEN`

To test Vault locally, start a dev server:

```bash
vault server -dev
export VAULT_ADDR=http://127.0.0.1:8200
vault kv put secret/asr-system/online ONLINE_API_TOKEN=dev-token
```

Then set `VAULT_ENABLED=true` and `VAULT_AUTH_METHOD=token` in `.env`.

## Rotation

- Rotate Vault AppRole `secret_id` at least every 90 days.
- Rotate application secrets in Vault; services pick up new values on next restart.
- On leak suspicion, rotate immediately and invalidate old keys in Vault.
