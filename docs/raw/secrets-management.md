# Secrets and Environment Management

## Principles

- No secrets in repository history.
- Local development uses `.env` from `.env.example`.
- CI/CD uses platform secret stores (GitHub Secrets, GitLab CI Variables, Vault).
- Production secrets are injected on the server and never committed.

## Scope separation

- Batch scope variables use `BATCH_*` prefix.
- Online scope variables use `ONLINE_*` prefix.
- Shared infrastructure variables keep explicit shared names (`DB_DSN`, etc.).

## Required CI/CD secrets

- `DEPLOY_HOST`
- `DEPLOY_USER`
- `DEPLOY_SSH_KEY`
- `REMOTE_APP_DIR`
- `GHCR_USERNAME`
- `GHCR_TOKEN`

## Local setup

```bash
cp .env.example .env
```

Then set non-empty values for private fields:
- `BATCH_STORAGE_ACCESS_KEY`
- `BATCH_STORAGE_SECRET_KEY`
- `ONLINE_API_TOKEN`

## Rotation

- Rotate registry and deploy secrets at least every 90 days.
- On leak suspicion, rotate immediately and invalidate old keys.
