# Airflow local stack

## Start

```bash
docker compose -f deploy/airflow/docker-compose.yml up -d
```

## Initialize DB and admin

```bash
docker exec -it airflow-webserver airflow db migrate
docker exec -it airflow-webserver airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com
```

The DAG `nightly_asr_batch` runs daily at `00:00` and has an SLA of 8 hours.
