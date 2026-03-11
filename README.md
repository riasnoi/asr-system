# ASR System for Call Center QA

MVP-система автоматической обработки звонков колл-центра из двух сервисов:
- `batch` контур: nightly обработка звонков через Airflow + Docker;
- `online` контур: API для доступа к карточкам звонков и агрегированным результатам.

Проект реализует pipeline: `ingest -> ASR -> speaker attribution -> emotion -> aggregation`.

## Архитектура

Код организован по Clean Architecture:
- `src/asr_system/domain` - сущности, value objects, доменные правила.
- `src/asr_system/application` - use cases (batch и online сценарии).
- `src/asr_system/infrastructure` - адаптеры моделей, хранилищ и файловых источников.
- `src/asr_system/interfaces/batch` - запуск batch-обработки (и интеграция с Airflow).
- `src/asr_system/interfaces/online` - online API.
- `services/batch` и `services/online` - отдельные deployable entrypoints.

## Структура репозитория

```text
asr-system/
├── docs/
│   ├── raw/
│   └── pdf/
├── services/
│   ├── batch/
│   └── online/
├── src/asr_system/
│   ├── application/
│   ├── domain/
│   ├── infrastructure/
│   ├── interfaces/
│   └── config.py
├── tests/
├── pyproject.toml          # будет добавлен в шаге зависимостей
├── uv.lock                 # будет добавлен в шаге зависимостей
└── README.md
```

## Локальный запуск

1. Подготовить окружение:
   - скопировать `.env.example` в `.env`;
   - заполнить переменные под локальную среду.
2. Синхронизировать зависимости:
   - `uv sync --frozen`
3. Запуск batch вручную:
   - `uv run python services/batch/main.py`
4. Запуск online API:
   - `uv run python services/online/main.py`

## API online-сервиса (MVP)

- `GET /health` - healthcheck.
- `GET /calls?min_negative_index=0.5` - список звонков по порогу индекса.
- `GET /calls/{call_id}` - карточка звонка (реплики + индексы).

## Воспроизводимость

- Конфигурация централизована в `src/asr_system/config.py`.
- Все env-переменные описаны в `.env.example`.
- Зависимости фиксируются через `pyproject.toml` и `uv.lock`.
- Результаты batch сохраняются в `utterances.jsonl` и `call_scores.jsonl`.

## Deploy и rollback

- Сборка происходит в CI после прохождения quality gates.
- Публикуются 2 образа: `asr-batch:<tag>` и `asr-online:<tag>`.
- CD запускается в push-модели: CI обновляет удаленный сервер по SSH.
- Rollback: переключение на предыдущий стабильный тег обоих сервисов.

## SLA и ограничения MVP

- Суточный batch должен завершаться до `08:00` МСК.
- Модельные адаптеры в текущем состоянии содержат stub-реализации, которые заменяются на production-интеграции.
- Для пилота приоритет: стабильный nightly workflow и релевантный top проблемных звонков.

## Документация

- Основной ML-документ: `docs/raw/ml-system-doc-v1.md`
- PDF-версия: `docs/pdf/ml-system-doc-v1.pdf`
