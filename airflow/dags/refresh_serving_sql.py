from datetime import datetime
from airflow import DAG
from airflow.providers.postgres.operators.postgres import PostgresOperator

with DAG(
    dag_id="refresh_serving_sql",
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["serving", "postgres", "mv"],
    default_args={"owner": "airflow"},
):
    refresh_daily = PostgresOperator(
        task_id="refresh_daily_avg_mv",
        postgres_conn_id="postgres_dw",
        sql="REFRESH MATERIALIZED VIEW aqi.daily_avg_mv;",
    )
    refresh_exceed = PostgresOperator(
        task_id="refresh_exceedance_30d_mv",
        postgres_conn_id="postgres_dw",
        sql="REFRESH MATERIALIZED VIEW aqi.exceedance_30d_mv;",
    )
    refresh_latest = PostgresOperator(
        task_id="refresh_latest_15min_mv",
        postgres_conn_id="postgres_dw",
        sql="REFRESH MATERIALIZED VIEW aqi.latest_15min_mv;",
    )

    refresh_daily >> refresh_exceed >> refresh_latest
