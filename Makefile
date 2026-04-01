.PHONY: install lint format test run-online run-batch build docker-build

install:
	uv sync --frozen --all-groups

lint:
	uv run black --check .
	uv run isort --check-only .
	uv run flake8 src tests services
	uv run pylint src/asr_system services/batch/main.py services/online/main.py
	uv run mypy src

format:
	uv run black .
	uv run isort .

test:
	uv run pytest

run-online:
	uv run python services/online/main.py

run-batch:
	uv run python services/batch/main.py

docker-build:
	docker build -f Dockerfile.online -t asr-online:local .
	docker build -f Dockerfile.batch -t asr-batch:local .
