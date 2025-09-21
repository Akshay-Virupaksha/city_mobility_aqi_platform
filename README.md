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
