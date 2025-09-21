City Mobility AQI Platform

End-to-end data engineering project that ingests real-world air-quality data, processes it with Spark, serves aggregates in Postgres, orchestrates jobs with Airflow, and publishes analytics to Tableau.

Pipeline (high level):
OpenAQ v3 → Kafka → Spark (Bronze/Silver/Gold) → Postgres (MVs) → Airflow (refresh + CSV exports) → Tableau
