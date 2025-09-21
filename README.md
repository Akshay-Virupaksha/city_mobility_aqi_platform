# City Mobility AQI Platform

**End-to-end data engineering project** that ingests real-world air-quality data, processes it with **Spark**, serves aggregates in **Postgres**, orchestrates jobs with **Airflow**, and publishes analytics to **Tableau**.

**Pipeline (high level):**  
`OpenAQ v3 → Kafka → Spark (Bronze/Silver/Gold) → Postgres (MVs) → Airflow (refresh + CSV exports) → Tableau`

---

## 🧭 Overview

- **Streaming ingest:** Python collector pushes OpenAQ v3 measurements to **Kafka** (`openaq.measurements`).
- **Spark processing:**
  - **Bronze:** write raw measurements from Kafka to partitioned **Parquet**.
  - **Silver:** clean/filter/select core columns.
  - **Gold:** 15-minute windowed **PM2.5** averages per location.
- **Serving:** **Postgres** schema `serving_dw.aqi` with materialized views (daily averages, 30-day exceedances, latest 15-min).
- **Orchestration:** **Airflow** DAGs to refresh SQL and export CSVs for BI.
- **Analytics:** **Tableau** dashboard (map, 15-min trend, calendar heatmap, exceedance leaderboard) + KPI strip.

---

## 📂 Repository layout

airflow/

dags/

export_openaq_dashboard_assets.py # exports CSVs for Tableau

refresh_serving_sql.py # REFRESH MATERIALIZED VIEWs

orchestrate_serving_and_exports.py # refresh → export
exports/ # CSV outputs (gitignored; .gitkeep kept)
collectors/
openaq_collector.py # live ingest
openaq_backfill.py # historical pull with rate-limit handling
spark/
openaq_kafka_to_parquet.py # Bronze (streaming)
openaq_silver_batch.py # Silver (batch)
openaq_gold_batch.py # Gold 15-min (batch)
openaq_gold_to_postgres.py # (optional) push gold to Postgres
sql/
aqi_schema.sql # schema, tables, indexes
aqi_views.sql # materialized views
dashboards/
tableau/city_mobility_aqi.twbx # packaged workbook
screenshots/ # images for README
scripts/
get_data.sh # fetch data from GitHub Releases
.env.example
docker-compose.yml
README.md


---

## ✅ Prerequisites

- **Docker Desktop** (Mac)
- **Python 3** (for small helper commands)
- **Git + GitHub CLI** (`brew install gh`) if you want to publish releases
- **Tableau Desktop** (or **Tableau Public** to publish the workbook)

---

## ⚡ Quick start (TL;DR)

```bash
# 0) clone and enter
git clone https://github.com/<your_github_username>/city_mobility_aqi_platform.git
cd city_mobility_aqi_platform

# 1) create .env from example (add your OpenAQ key + a Fernet key)
cp .env.example .env
# generate a proper Fernet key (44 chars)
python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
# paste it into .env: AIRFLOW__CORE__FERNET_KEY=...

# 2) bring up infra
docker compose up -d kafka postgres airflow-webserver airflow-scheduler

# 3) create Airflow admin (then open http://localhost:8080)
docker compose exec airflow-webserver \
  airflow users create --role Admin --username admin --password admin \
  --firstname You --lastname Admin --email you@example.com

# 4) create Kafka topic
docker compose exec kafka /opt/bitnami/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --create --topic openaq.measurements \
  --partitions 3 --replication-factor 1 --if-not-exists

# 5) start live ingest (collector → Kafka)
docker compose up -d collector-openaq

# 6) start Bronze streaming (Kafka → Parquet)
docker compose up -d spark-openaq-bronze

# 7) run Silver and Gold batches once
docker compose run --rm spark-runner \
  /opt/bitnami/spark/bin/spark-submit --master 'local[*]' /app/spark/openaq_silver_batch.py

docker compose run --rm spark-runner \
  /opt/bitnami/spark/bin/spark-submit --master 'local[*]' /app/spark/openaq_gold_batch.py

# 8) load Postgres schema + views
docker compose exec -T postgres psql -U mobility -d serving_dw -f /app/sql/aqi_schema.sql
docker compose exec -T postgres psql -U mobility -d serving_dw -f /app/sql/aqi_views.sql

# 9) add Airflow connection to Postgres (UI → Admin → Connections → +)
# Conn Id: postgres_dw, Type: Postgres, Host: postgres, Schema: serving_dw, Login: mobility, Password: mobility, Port: 5432

# 10) run orchestration (SQL refresh → CSV exports)
docker compose exec -T airflow-scheduler airflow dags trigger orchestrate_serving_and_exports

# 11) open Tableau workbook and Refresh
# dashboards/tableau/city_mobility_aqi.twbx, data sources point to airflow/dags/exports/*.csv

```

## ⚙️ Configuration (.env)

- Copy .env.example to .env and fill:

## Airflow
AIRFLOW__CORE__FERNET_KEY=REPLACE_WITH_44_CHAR_URLSAFE_BASE64

## OpenAQ v3 (create a free key on OpenAQ)
OPENAQ_API_KEY=REPLACE_WITH_YOUR_KEY
OPENAQ_BASE_URL=https://api.openaq.org/v3

## Postgres
POSTGRES_DB=serving_dw
POSTGRES_USER=mobility
POSTGRES_PASSWORD=mobility

Do not commit .env.

## 🧪 Bringing up the stack

```bash
docker compose up -d kafka postgres airflow-webserver airflow-scheduler
docker compose ps
```

- Create an admin user if needed (see quick start).

## 📡 Kafka + ingest

```bash
docker compose exec kafka /opt/bitnami/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --create --topic openaq.measurements \
  --partitions 3 --replication-factor 1 --if-not-exists
```

- Live collector:

```bash
docker compose up -d collector-openaq
# optional: peek
docker compose exec kafka /opt/bitnami/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic openaq.measurements --from-beginning --max-messages 5
```

- Backfill (optional; handles rate limits, can be slow):

```bash
docker compose run --rm backfill-openaq
```

## 🔥 Spark processing

- Bronze (streaming)

```bash
docker compose up -d spark-openaq-bronze
#output: data/bronze/openaq/event_date=YYYY-MM-DD/*.parquet
```

- Silver (batch)

```bash
docker compose run --rm spark-runner \
  /opt/bitnami/spark/bin/spark-submit --master 'local[*]' /app/spark/openaq_silver_batch.py
# output: data/silver/openaq/...
```

- Gold 15-minute aggregates (batch)

```bash
docker compose run --rm spark-runner \
  /opt/bitnami/spark/bin/spark-submit --master 'local[*]' /app/spark/openaq_gold_batch.py
# output: data/gold/openaq_15min/*.parquet
```

- Quick row counts (sanity):

```bash
docker compose run --rm spark-runner \
  bash -lc "python - <<'PY'\nimport pandas as pd;print('gold rows:',len(pd.read_parquet('/app/data/gold/openaq_15min')))\nPY"
```

## 🗄️ Postgres serving layer

- Load schema and views:

```bash
docker compose exec -T postgres psql -U mobility -d serving_dw -f /app/sql/aqi_schema.sql
docker compose exec -T postgres psql -U mobility -d serving_dw -f /app/sql/aqi_views.sql
```

- Check counts:

```bash
docker compose exec -T postgres psql -U mobility -d serving_dw -c "SELECT COUNT(*) FROM aqi.openaq_15min;"
docker compose exec -T postgres psql -U mobility -d serving_dw -c "SELECT COUNT(*) FROM aqi.daily_avg_mv;"
```

## ⏱️ Airflow orchestration

DAGs live in airflow/dags/:

- refresh_serving_sql — refreshes Postgres materialized views.

- export_openaq_dashboard_assets — writes CSVs for Tableau:

-- airflow/dags/exports/ts_15min.csv

-- airflow/dags/exports/daily.csv

-- airflow/dags/exports/exceedance_30d.csv

-- airflow/dags/exports/latest_map.csv

- orchestrate_serving_and_exports — runs SQL refresh → then exports.

Setup:

1. Airflow UI → Admin → Connections → add postgres_dw (see Quick start).

2. Trigger orchestration:

```bash
docker compose exec -T airflow-scheduler airflow dags trigger orchestrate_serving_and_exports
```

3. CSV sanity:

```bash
ls -lh airflow/dags/exports/*.csv
wc -l airflow/dags/exports/*.csv | sed -n '1,20p'
```







