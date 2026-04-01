# Triton Inference Server -- ML-сервер

Инструкция по развёртыванию Whisper и ruBERT на отдельном GPU-сервере.

## Требования

- Ubuntu 22.04 / 24.04
- NVIDIA GPU (рекомендуется A10, L4, T4 или лучше)
- NVIDIA Driver 535+
- Docker + NVIDIA Container Toolkit **или** k3s + NVIDIA GPU Operator

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

На основном сервере (Сервер 1) обновите ConfigMap с IP ML-сервера:

```bash
kubectl -n asr-system edit configmap asr-config
```

Замените `TRITON_SERVER_IP` на реальный IP:

```yaml
BATCH_ASR_PROVIDER: "remote"
BATCH_ASR_REMOTE_URL: "http://<ML_SERVER_IP>:30800"
BATCH_EMOTION_PROVIDER: "remote"
BATCH_EMOTION_REMOTE_URL: "http://<ML_SERVER_IP>:30800"
```

Перезапустите batch-поды:

```bash
kubectl -n asr-system rollout restart deployment/asr-online
```

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
