# Final Acceptance Checklist

## Architecture and code quality

- [x] Clean Architecture applied (`domain`, `application`, `infrastructure`, `interfaces`).
- [x] Batch and online services are separated (`services/batch`, `services/online`).
- [x] Centralized environment interface via `src/asr_system/config.py`.

## Testing and static checks

- [x] Unit tests exist and run with coverage threshold.
- [x] Coverage gate configured (`--cov-fail-under=80`).
- [x] CI includes `black`, `isort`, `flake8`, `pylint`, `mypy`, `pytest`.

## Packaging and runtime

- [x] Dependency pinning via `pyproject.toml` and `uv.lock`.
- [x] Separate Dockerfiles for batch and online.
- [x] Airflow DAG scaffold for nightly batch exists.

## Delivery and operations

- [x] Registry publication workflow for images exists.
- [x] Push-based CD workflow to remote server exists.
- [x] Rollback script exists.
- [x] Secrets policy documented and `.env.example` provided.

## Verification commands

```bash
python3 -m uv sync --frozen --all-groups
python3 -m uv run black --check .
python3 -m uv run isort --check-only .
python3 -m uv run flake8 src tests services
python3 -m uv run pylint src/asr_system services/batch/main.py services/online/main.py
python3 -m uv run mypy src
python3 -m uv run pytest
```
