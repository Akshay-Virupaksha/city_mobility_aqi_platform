from datetime import datetime
from airflow import DAG
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

with DAG(
    dag_id="orchestrate_serving_and_exports",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["orchestration", "tableau"],
):
   
    refresh_sql = TriggerDagRunOperator(
        task_id="refresh_sql",
        trigger_dag_id="refresh_serving_sql",
        reset_dag_run=True,
        wait_for_completion=True,
    )

    
    export_assets = TriggerDagRunOperator(
        task_id="export_dashboard_assets",
        trigger_dag_id="export_openaq_dashboard_assets",
        reset_dag_run=True,
        wait_for_completion=True,
    )

    refresh_sql >> export_assets
