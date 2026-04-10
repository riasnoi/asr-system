# Восстановление после бэкапа / пересоздания серверов

Краткий порядок действий, который уже срабатывал на практике (основной сервер с Airflow/online и отдельный GPU-сервер с Triton). Подставьте свои имена нод, IP и пути при необходимости.

---

## 1. GPU-сервер (k3s + Triton, namespace `ml-inference`)

### 1.1. Имя ноды и метка для NVIDIA Device Plugin

```bash
export KUBECONFIG="${HOME}/.kube/config"
# Если файла нет — см. раздел «Основной сервер», пункт про kubeconfig.

NODE_NAME=$(kubectl get nodes -o jsonpath='{.items[0].metadata.name}')
echo "NODE_NAME=${NODE_NAME}"

kubectl label node "${NODE_NAME}" nvidia.com/gpu.present=true --overwrite
```

### 1.2. Режим NVIDIA Container Runtime (`legacy`)

Без этого device plugin может падать с `ERROR_LIBRARY_NOT_FOUND` (NVML).

```bash
sudo sed -i 's/^mode = "auto"/mode = "legacy"/' /etc/nvidia-container-runtime/config.toml
sudo cp /etc/nvidia-container-runtime/config.toml /etc/nvidia-container-runtime/config.toml.tmpl 2>/dev/null || true
sudo systemctl restart k3s
sleep 45
kubectl get pods -n nvidia-device-plugin
```

Ожидаем под device plugin в состоянии **Running**.

### 1.3. Triton в `Pending`: несовпадение `PersistentVolume` и hostname ноды

Типичное сообщение в `kubectl describe pod`:

`didn't match PersistentVolume's node affinity`

После смены hostname ноды старый PV указывает на прежнее имя. Действия:

```bash
kubectl scale deployment triton -n ml-inference --replicas=0
kubectl wait --for=delete pod -l app=triton -n ml-inference --timeout=120s 2>/dev/null || true

kubectl delete pvc triton-models-pvc triton-hf-cache-pvc -n ml-inference --wait=true

# Удалить старые PV, если остались (имена посмотреть: kubectl get pv)
# kubectl delete pv <имя-models-pv> <имя-hf-cache-pv>
```

Каталоги на хосте под **local**-тома:

```bash
sudo mkdir -p /opt/triton-models /opt/triton-hf-cache
sudo chmod 777 /opt/triton-models /opt/triton-hf-cache
```

Создать **два** PV с `nodeAffinity` на **текущую** ноду (`NODE_NAME` — как выше) и путями `/opt/triton-models`, `/opt/triton-hf-cache` (см. пример в истории деплоя: `local.path` + `kubernetes.io/hostname` In `NODE_NAME`). Затем PVC с `storageClassName: ""` и `volumeName`, указывающим на эти PV.

Залить модели (если нет локального бэкапа — из репозитория):

```bash
cd /tmp && rm -rf asr-system && git clone --depth 1 https://github.com/riasnoi/asr-system.git
sudo rsync -a /tmp/asr-system/deploy/triton/model_repository/ /opt/triton-models/
ls /opt/triton-models   # ожидаются каталоги rubert-tiny2, whisper-large-v3-turbo
```

Поднять Triton:

```bash
kubectl scale deployment triton -n ml-inference --replicas=1
kubectl get pods -n ml-inference -w
```

Дождаться **READY 1/1**.

### 1.4. Проверка Triton по HTTP (NodePort)

Узнать порт:

```bash
kubectl get svc -n ml-inference
```

Для сервиса с маппингом `8000:30800/TCP` HTTP API на ноде — **порт 30800** (не путать с другими NodePort).

```bash
curl -sv http://127.0.0.1:30800/v2/health/ready
curl -s -X POST http://127.0.0.1:30800/v2/repository/index \
  -H "Content-Type: application/json" -d '{}' | python3 -m json.tool
```

Ожидается `200` на `/v2/health/ready` и список моделей в состоянии **READY**.

Альтернатива без NodePort: `kubectl port-forward -n ml-inference svc/triton 8000:8000` и обращаться к `http://127.0.0.1:8000`.

### 1.5. Модель эмоций (ruBERT) в Triton

В `deploy/triton/model_repository/rubert-tiny2/1/model.py` должна быть маппинг CEDR-лейблов (`joy`, `sadness`, `anger`, `no_emotion`, …) в доменные (`positive`, `sad`, `angry`, `neutral`). Иначе скоринг в приложении будет вести себя как при одних нейтральных эмоциях. После правки файла на диске — перезагрузка модели в Triton или обновление файла на томе моделей и sync через CI **Deploy Triton** (с опцией копирования `model_repository`).

---

## 2. Основной сервер (k3s + `asr-system`: online, Airflow)

### 2.1. `kubectl`: отсутствует kubeconfig

Симптом: `connection to the server localhost:8080 was refused`.

```bash
mkdir -p "${HOME}/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "${HOME}/.kube/config"
sudo chown "$(id -u):$(id -g)" "${HOME}/.kube/config"
chmod 600 "${HOME}/.kube/config"
export KUBECONFIG="${HOME}/.kube/config"

kubectl cluster-info
kubectl get nodes
```

Чтобы не забывать после новой SSH-сессии:

```bash
echo 'export KUBECONFIG="${HOME}/.kube/config"' >> ~/.bashrc
```

### 2.2. Vault на хосте

```bash
sudo systemctl start vault 2>/dev/null || true
export VAULT_ADDR="http://127.0.0.1:8200"
vault status
```

Если **Sealed: true** — выполнить `vault operator unseal` нужное число раз (ключи хранить вне сервера).

### 2.3. Адрес Vault для подов (не `127.0.0.1`)

Внутри контейнера `127.0.0.1` — это не хост. В ConfigMap должен быть **IP или DNS хоста**, доступный с подов (часто IP основного сервера в LAN):

```bash
export VAULT_HOST_IP="<IP_хоста_где_крутится_Vault>"
kubectl -n asr-system patch configmap asr-config --type merge -p \
  "{\"data\":{\"VAULT_ADDR\":\"http://${VAULT_HOST_IP}:8200\"}}"
```

При сбросе AppRole в Vault — обновить секрет Kubernetes `asr-vault-credentials` (`VAULT_ROLE_ID`, `VAULT_SECRET_ID`) и перезапустить поды, которые ходят в Vault.

### 2.4. URL GPU / Triton для приложения

Если основной кластер **не** содержит Triton в том же Kubernetes, в Vault (путь вида `secret/asr-system/batch` в KV v2) задаются:

- `BATCH_ASR_REMOTE_URL`
- `BATCH_EMOTION_REMOTE_URL`

Формат: `http://<IP_или_DNS_GPU_сервера>:<NodePort_HTTP>` (например порт **30800**, если так настроен сервис Triton).

После изменения секретов в Vault:

```bash
kubectl rollout restart deployment/asr-online -n asr-system
kubectl rollout restart deployment/airflow-scheduler -n asr-system
```

(Процесс онлайн-сервиса кэширует настройки; без рестарта новый URL не подхватится.)

### 2.5. ConfigMap приложения и DAG Airflow

```bash
cd /opt/asr-system/deploy/k8s/base
kubectl apply -f configmap.yaml
```

Если в ConfigMap DAG остался образ-заглушка `asr-batch:placeholder`, подставить реальный образ из CronJob:

```bash
BATCH_IMAGE=$(kubectl get cronjob -n asr-system -o jsonpath='{.items[0].spec.jobTemplate.spec.template.spec.containers[0].image}')
kubectl get configmap airflow-dags -n asr-system -o yaml \
  | sed "s|asr-batch:placeholder|${BATCH_IMAGE}|g" \
  | kubectl apply -f -
```

Перезапуски:

```bash
kubectl rollout restart deployment/asr-online -n asr-system
kubectl rollout restart deployment/airflow-scheduler -n asr-system
kubectl rollout restart deployment/airflow-webserver -n asr-system
```

Проверка:

```bash
kubectl get pods -n asr-system
kubectl logs -n asr-system deployment/airflow-scheduler --tail=50
```

В логах не должно быть постоянных ошибок подключения к Vault и `invalid role or secret ID` (при корректных credentials).

---

## 3. Проверка сквозного сценария

1. С основного сервера: `curl -s -o /dev/null -w "%{http_code}\n" "http://<GPU_IP>:30800/v2/health/ready"` → **200**.
2. Загрузка звонка через online API: в логах `asr-online` — успешные HTTP-запросы к Triton (ASR и rubert).
3. Airflow: ручной прогон DAG или ожидание расписания; поды задач стартуют без `ImagePullBackOff` и с корректным образом batch.

---

## 4. Что заранее вынести из «головы» в надёжное хранилище

- Ключи unseal Vault и доступ к KV (роли AppRole).
- Актуальный **IP или DNS** GPU-сервера и порт NodePort HTTP Triton.
- Копия или доступ к репозиторию `asr-system` для восстановления `model_repository` на GPU без ручного поиска файлов.

После восстановления диска путь `/opt/asr-system` может быть без `.git` — нормально: актуальные манифесты подтягиваются CI/CD на сервер; для ручного применения используйте файлы с диска или свежий клон репозитория.
