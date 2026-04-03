# Triton Inference Server -- ML-сервер

Инструкция по развёртыванию Whisper и ruBERT на отдельном GPU-сервере.

## Требования

- Ubuntu 22.04 / 24.04
- NVIDIA GPU (рекомендуется A10, L4, T4 или лучше)
- NVIDIA Driver 535+
- Docker + NVIDIA Container Toolkit **или** k3s + NVIDIA GPU Operator

## CI/CD (GitHub Actions)

Workflow **Deploy Triton (ML server)** (`.github/workflows/deploy-triton.yml`) запускается **только вручную** (Actions → Run workflow). Обычные пуши в репозиторий его не вызывают, поэтому поды Triton и загруженные веса не перезапускаются из‑за коммитов в код приложения.

На сервере нужны те же GitHub Secrets, что и для основного деплоя, но с префиксом `TRITON_*` (см. `docs/raw/secrets-management.md`). Скрипт делает `kubectl apply` **без** `rollout restart`: новый rollout случится только если изменился spec Deployment (образ, ресурсы, пробы и т.д.).

Параметр **sync model repository**:

- **выключен (по умолчанию)** — обновляются только файлы на диске сервера и манифесты; если YAML не менялся, поды остаются как были.
- **включить** — после apply выполняется `kubectl cp` каталога `model_repository` в `/models` в поде (первый вывод в строй или обновление `model.py` / `config.pbtxt`). При смене Python backend может понадобиться перезагрузка модели в Triton вручную.

Первый раз имеет смысл запустить workflow с **sync model repository = true**, чтобы скопировать backend-файлы в PVC.

## Вариант 1: K8s (k3s)

### 1. Установить k3s

```bash
curl -sfL https://get.k3s.io | sh -
```

### 2. Установить NVIDIA GPU Operator

```bash
# Добавить Helm-репозиторий NVIDIA
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia
helm repo update

# Установить GPU Operator (автоматически настроит драйверы и device plugin)
helm install gpu-operator nvidia/gpu-operator \
  --namespace gpu-operator --create-namespace \
  --set driver.enabled=false  # если драйвер уже установлен вручную
```

Проверить, что GPU видна:

```bash
kubectl get nodes -o json | grep nvidia.com/gpu
```

### 3. Скопировать model_repository на сервер

```bash
# С локальной машины
scp -r deploy/triton/model_repository root@<ML_SERVER_IP>:/opt/triton/models
```

### 4. Установить зависимости моделей в PVC

Модели скачиваются при первом запуске Triton. Для ускорения предзагрузите их:

```bash
# На ML-сервере
pip install faster-whisper transformers torch

# Предзагрузка Whisper (скачает ~3GB)
python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo')"

# Предзагрузка ruBERT (скачает ~100MB)
python -c "from transformers import pipeline; pipeline('text-classification', model='cointegrated/rubert-tiny2-cedr-emotion-detection')"
```

### 5. Применить K8s манифесты

```bash
kubectl apply -f deploy/triton/k8s/namespace.yaml
kubectl apply -f deploy/triton/k8s/triton-pvc.yaml
kubectl apply -f deploy/triton/k8s/triton-deployment.yaml
kubectl apply -f deploy/triton/k8s/triton-service.yaml
```

### 6. Скопировать модели в PVC

```bash
# Найти Pod
POD=$(kubectl -n ml-inference get pod -l app=triton -o name | head -1)

# Скопировать model_repository в PVC
kubectl -n ml-inference cp /opt/triton/models/ ${POD}:/models/
```

### 7. Проверить

```bash
# Health check
curl http://localhost:30800/v2/health/ready

# Список моделей
curl http://localhost:30800/v2/models
```

## Вариант 2: Docker Compose

```bash
cd deploy/triton
docker compose up -d
```

Проверить:

```bash
curl http://localhost:8000/v2/health/ready
curl http://localhost:8000/v2/models
```

## Подключение к ASR-системе

В **production** (`VAULT_ENABLED=true`, как в `deploy/k8s/base/configmap.yaml`) приложение подставляет batch-настройки из **Vault**, а не из ConfigMap. ConfigMap `asr-config` хранит в основном несекретное окружение и параметры доступа к Vault; URL Triton туда класть не нужно.

Добавьте или обновите ключи в **`secret/data/asr-system/batch`** (см. пример команд в `docs/raw/secrets-management.md`):

- `BATCH_ASR_PROVIDER=remote`
- `BATCH_ASR_REMOTE_URL=http://<ML_SERVER_IP>:30800` (или `:8000` для Docker Compose без NodePort)
- `BATCH_EMOTION_PROVIDER=remote`
- `BATCH_EMOTION_REMOTE_URL` — тот же базовый URL, что и для ASR

После смены значений в Vault **новый** batch-pod (например, следующий запуск **CronJob**) подхватит их сам. Перезапуск `asr-online` для этого не требуется, если online-сервис не ходит в Triton.

Локально (`VAULT_ENABLED=false`) те же переменные задаются в **`.env`** рядом с `BATCH_STORAGE_*`.

## Тестирование inference

```bash
# Whisper
curl -X POST http://<ML_SERVER_IP>:30800/v2/models/whisper/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [{
      "name": "AUDIO_DATA",
      "shape": [1],
      "datatype": "BYTES",
      "data": ["<base64-encoded-audio>"]
    }],
    "outputs": [{"name": "SEGMENTS"}]
  }'

# Emotion
curl -X POST http://<ML_SERVER_IP>:30800/v2/models/rubert_emotion/infer \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": [{
      "name": "TEXT",
      "shape": [1],
      "datatype": "BYTES",
      "data": ["У меня проблема с заказом"]
    }],
    "outputs": [{"name": "EMOTION"}, {"name": "CONFIDENCE"}]
  }'
```

## Структура файлов

```
deploy/triton/
├── docker-compose.yml          # Docker Compose (альтернатива K8s)
├── k8s/
│   ├── namespace.yaml
│   ├── triton-deployment.yaml  # GPU deployment
│   ├── triton-pvc.yaml         # 20Gi для моделей
│   └── triton-service.yaml     # NodePort :30800
├── model_repository/
│   ├── whisper/
│   │   ├── config.pbtxt
│   │   └── 1/model.py          # faster-whisper backend
│   └── rubert_emotion/
│       ├── config.pbtxt
│       └── 1/model.py          # transformers backend
└── README.md
```
