# Secrets and Environment Management

## Principles

- No secrets in repository history.
- Local development uses `.env` from `.env.example` (`VAULT_ENABLED=false`).
- Production uses HashiCorp Vault via `VAULT_ENABLED=true`.
- GitHub Actions **не** подставляет прикладные секреты (`BATCH_*`, `ONLINE_*` и т.д.) из Vault в манифесты: их при старте читает приложение (и Airflow — своим Vault backend), используя только bootstrap **AppRole** из окружения пода.
- Секрет Kubernetes `asr-vault-credentials` (`VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID`) создаётся **на кластере вручную** (шаблон: `deploy/k8s/base/secret.yaml`); workflow `deploy.yml` его сейчас не генерирует.

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

1. В Kubernetes в namespace `asr-system` существует Secret **`asr-vault-credentials`** с `VAULT_ADDR`, `VAULT_ROLE_ID`, `VAULT_SECRET_ID` (и при необходимости другими ключами, которые ожидает образ). Pod’ы монтируют его через `envFrom` вместе с ConfigMap `asr-config` (`VAULT_ENABLED=true`, mount path и т.д.).
2. При старте процесса `config.py` вызывает `VaultSecretsProvider`: по AppRole открывается KV `secret/data/asr-system/{app,batch,online}` и значения подмешиваются в настройки.
3. Сценарий **docker-compose** (`scripts/deploy/deploy_remote.sh`): на диск пишется только `.env` с bootstrap Vault — прикладные ключи по-прежнему с Vault при старте контейнера.
4. Airflow использует нативный Vault Secrets Backend (`airflow-providers-hashicorp`) для connections/variables.

### Первичная настройка Vault и кластера (чеклист)

**A. Vault (один раз, админом Vault)**

1. Включить KV v2 на mount `secret` (или другой — тогда поправьте `VAULT_MOUNT_POINT` в ConfigMap).
2. Создать данные под пути (префикс `asr-system` задаётся `VAULT_BASE_PATH` в ConfigMap):

```bash
# Shared ASR database — app DSN + deploy-time postgres credentials in one secret:
vault kv put secret/asr-system/app \
  DB_DSN="postgresql://asr_user:asr_password@asr-db:5432/asr" \
  POSTGRES_USER="asr_user" \
  POSTGRES_PASSWORD="asr_password"
# DB_DSN is read by the application at runtime (psycopg2).
# POSTGRES_USER / POSTGRES_PASSWORD are read by k8s_deploy.sh at deploy time
# to create the asr-db-credentials K8s Secret.

# batch: хранилище + при необходимости Triton (см. также раздел с vault kv patch ниже)
vault kv put secret/asr-system/batch \
  BATCH_STORAGE_ACCESS_KEY="..." \
  BATCH_STORAGE_SECRET_KEY="..." \
  BATCH_ASR_PROVIDER=remote \
  BATCH_ASR_REMOTE_URL="http://<ML_IP>:30800" \
  BATCH_EMOTION_PROVIDER=remote \
  BATCH_EMOTION_REMOTE_URL="http://<ML_IP>:30800"

vault kv put secret/asr-system/online ONLINE_API_TOKEN="..."

# Airflow (если используете Vault для БД Airflow)
vault kv put secret/asr-system/airflow POSTGRES_USER="..." POSTGRES_PASSWORD="..."
```

3. Создать **политику** с `read` на нужные пути (минимум `secret/data/asr-system/app`, `batch`, `online` — по роли сервиса).
4. Создать **AppRole**, привязать политику; сохранить **`role_id`** и выпустить **`secret_id`** для подов.

**B. Kubernetes**

```bash
kubectl -n asr-system create secret generic asr-vault-credentials \
  --from-literal=VAULT_ADDR="https://vault.example.com:8200" \
  --from-literal=VAULT_ROLE_ID="<role_id>" \
  --from-literal=VAULT_SECRET_ID="<secret_id>"
```

Убедитесь, что с подов кластера **доступен** `VAULT_ADDR` (DNS, TLS, firewall).

**C. CI/CD (GitHub)**

В репозитории достаточно секретов для **SSH и GHCR** (`DEPLOY_HOST`, `GHCR_PAT`, …) — см. раздел выше. **Прикладные** ключи в GitHub Secrets **дублировать не обязательно**: они живут в Vault. После изменения данных в Vault новый запуск batch (новый pod) или перезапуск deployment подхватит значения без правки workflow.

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

> DB credentials (`POSTGRES_USER`, `POSTGRES_PASSWORD`) are read by the deploy script
> **directly from Vault on the target server** — no need to duplicate them in GitHub Secrets.

### Deploy-time Vault access (one-time server setup)

The deploy script reads `POSTGRES_USER` and `POSTGRES_PASSWORD` from
`secret/asr-system/app` at deploy time using the `vault` CLI.
It looks for a token in `/etc/vault-deploy.token` (or `$VAULT_DEPLOY_TOKEN_FILE`).

```bash
# On the server — create a Vault policy and a long-lived token for deploy:
vault policy write asr-deploy - <<'EOF'
path "secret/data/asr-system/app" { capabilities = ["read"] }
EOF

vault token create \
  -policy=asr-deploy \
  -display-name="asr-deploy" \
  -period=8760h \   # 1 year; rotate annually
  -field=token \
  | sudo tee /etc/vault-deploy.token
sudo chmod 600 /etc/vault-deploy.token
```

> `$VAULT_ADDR` is picked up from the environment; it defaults to `http://127.0.0.1:8200`.
> If your Vault listens on a different address, set `VAULT_ADDR` in `/etc/environment`
> or prefix it when running the script.

### Triton / ML server (optional, separate from main K8s deploy)

Workflow: `.github/workflows/deploy-triton.yml` (only **workflow_dispatch** — pushes to the repo do not run it).

- `TRITON_DEPLOY_HOST` — SSH host of the GPU / Triton machine (can match `DEPLOY_HOST` if the same box).
- `TRITON_DEPLOY_USER`
- `TRITON_DEPLOY_SSH_KEY`
- `TRITON_REMOTE_APP_DIR` — same idea as `REMOTE_APP_DIR` (directory where `deploy/triton` and `scripts/deploy/` are uploaded).

## Local setup

```bash
cp .env.example .env
```

With `VAULT_ENABLED=false` (default), set values directly in `.env`:
- `BATCH_STORAGE_ACCESS_KEY`
- `BATCH_STORAGE_SECRET_KEY`
- `ONLINE_API_TOKEN`
- при работе batch через удалённый Triton: `BATCH_ASR_PROVIDER`, `BATCH_ASR_REMOTE_URL`, `BATCH_EMOTION_PROVIDER`, `BATCH_EMOTION_REMOTE_URL` (см. `.env.example`)

### Пример: batch → Triton на отдельном сервере (KV `asr-system/batch`)

Адрес ML-сервера храните в том же секрете `batch/`, что и ключи S3 — приложение читает scope `batch` целиком при старте.

```bash
# подставьте IP/порт (K8s NodePort обычно 30800; docker compose на ML — 8000)
ML_URL="http://<ML_SERVER_IP>:30800"

vault kv patch secret/asr-system/batch \
  BATCH_ASR_PROVIDER=remote \
  BATCH_ASR_REMOTE_URL="${ML_URL}" \
  BATCH_EMOTION_PROVIDER=remote \
  BATCH_EMOTION_REMOTE_URL="${ML_URL}"
```

Если `vault kv patch` недоступен, обновите ключи через UI Vault или `vault kv get` / `vault kv put` с полным набором полей секрета `batch` (осторожно: `put` перезаписывает все ключи версии).

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
