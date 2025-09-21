from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

def say_hello():
    print("Airflow is up. We'll orchestrate ingestion and Spark next!")

with DAG(
    dag_id="hello_pipeline",
    start_date=datetime(2025, 1, 1),
    schedule_interval="@hourly",
    catchup=False,
    default_args={"retries": 1, "retry_delay": timedelta(minutes=2)},
    tags=["healthcheck"],
):
    PythonOperator(task_id="hello", python_callable=say_hello)
