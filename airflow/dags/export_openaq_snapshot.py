from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os

DATA_DIR = "/opt/airflow/exports"
SRC = "/opt/airflow/data/gold/openaq_15min"
OUT = f"{DATA_DIR}/openaq_snapshot.csv"

def export_csv():
    import pandas as pd
    print("Checking paths...")
    print("SRC exists:", os.path.exists(SRC))
    print("DATA_DIR exists:", os.path.exists(DATA_DIR))
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Reading parquet from:", SRC)
    df = pd.read_parquet(SRC)
    print("Rows read:", len(df))
    df = df.sort_values("window_start").tail(5000)
    df.to_csv(OUT, index=False)
    print("Wrote CSV:", OUT, "rows:", len(df))

with DAG(
    dag_id="export_openaq_snapshot",
    start_date=datetime(2025, 1, 1),
    schedule_interval="@hourly",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["export","snapshot"],
):
    PythonOperator(task_id="export_csv", python_callable=export_csv)