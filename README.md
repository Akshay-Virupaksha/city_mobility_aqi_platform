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

```bash
city_mobility_aqi_platform/
│── airflow/
│   └── dags/
│       │── export_openaq_dashboard_assets.py   # Exports CSVs for Tableau
│       │── refresh_serving_sql.py              # REFRESH MATERIALIZED VIEWs
│       │── orchestrate_serving_and_exports.py  # refresh → export orchestration
│       └── exports/                            # Generated CSVs (gitignored; keep .gitkeep)
│
│── collectors/
│   │── openaq_collector.py                     # Live ingest (OpenAQ → Kafka)
│   └── openaq_backfill.py                      # Historical pull with rate-limit handling
│
│── spark/
│   │── openaq_kafka_to_parquet.py              # Bronze (Kafka → Parquet, streaming)
│   │── openaq_silver_batch.py                  # Silver (batch cleaning)
│   │── openaq_gold_batch.py                    # Gold 15-min aggregates (batch)
│   └── openaq_gold_to_postgres.py              # (optional) push gold to Postgres
│
│── sql/
│   │── aqi_schema.sql                          # Tables, schema, indexes
│   └── aqi_views.sql                           # Materialized views (daily, 30d exceed, latest)
│
│── dashboards/
│   │── screenshots/                            # PNGs for README
│   └── tableau/
│       └── city_mobility_aqi.twbx              # Packaged Tableau workbook
│
│── scripts/
│   └── get_data.sh                             # Fetch data from GitHub Releases
│
│── data/                                       # Generated artifacts (gitignored)
│   │── bronze/
│   │── silver/
│   └── gold/
│
│── .env.example
│── .gitignore
│── docker-compose.yml
│── README.md                                 


```


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

--> airflow/dags/exports/ts_15min.csv

--> airflow/dags/exports/daily.csv

--> airflow/dags/exports/exceedance_30d.csv

--> airflow/dags/exports/latest_map.csv

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

## 📊 Tableau

- Open dashboards/tableau/city_mobility_aqi.twbx.

- Data sources point to the CSVs in airflow/dags/exports/.

- Click Data → Refresh All.

Sheets included:

- Map: latest PM2.5 by location (WHO/EPA color threshold parameter).

- 15-min Trend: time series for selected locations.

- Calendar (Daily Avg): heatmap by day.

- Exceedance Leaderboard (30d).

- KPI strip: active locations, 24h median, 30d exceed days, last ingest.

Tip: If a timestamp shows as string, set the field type to Date & Time in Tableau (exports are ISO-8601 UTC).

## 🚀 Run & Data

You have two choices:

A) Generate data locally (full pipeline)

Follow Quick start. CSVs for Tableau will appear under airflow/dags/exports/.

B) Download prebuilt data (free, via GitHub Releases)

Large datasets are published as release assets so the repo stays small.

```bash
bash scripts/get_data.sh
```

This downloads the release ZIP and extracts:

- data/gold/ (Parquet, 15-min gold)

- airflow/dags/exports/ (CSV files for Tableau)

Now open the Tableau workbook and refresh.

## 🛠️ Troubleshooting

Airflow “Fernet key” error
Generate a 44-char key:

```bash
python3 -c 'import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())'
```

Put it in .env → AIRFLOW__CORE__FERNET_KEY=..., then recreate webserver + scheduler.

Airflow can’t see DAGs
Verify the bind mount in docker-compose.yml maps ./airflow/dags:/opt/airflow/dags.
Check:

```bash
docker compose exec -T airflow-scheduler ls /opt/airflow/dags
```

Tableau only shows one month on the calendar
Ensure daily.csv has multiple months; re-run export_openaq_dashboard_assets to refresh.
Confirm Tableau field type is Date and you’re using Month on columns (not a single discrete month).

Backfill hits 429 (rate limits)
Re-run later; the backfill script paginates and respects limits.

### 🧱 Design choices

- CSV exports for Tableau: works with Tableau Public and makes publishing easy.

- Postgres materialized views: fast, resumable refresh, familiar SQL surface.

- Kafka + Spark: demonstrates streaming ingest and structured streaming for resume-ready skills.

- Docker Compose: quick local orchestration without cloud dependencies.

## 🗺️ Roadmap (nice-to-have)

- Data quality checks in Airflow (null/range checks).

- Incremental MV refresh logic.

- Streamlit or Superset as a secondary consumer.

- CI to lint Python and validate docker compose config.

## 🙌 Credits

- Data from OpenAQ (v3 API).

- Bitnami containers for Kafka/Spark.

- Apache Airflow, Apache Spark, PostgreSQL, Tableau.


## 📝 Notes

- .env is never committed. Example variables live in .env.example.

- Large data is distributed via GitHub Releases. The repo only keeps code, SQL, DAGs, and the Tableau workbook.






