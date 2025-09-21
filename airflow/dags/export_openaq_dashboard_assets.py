from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import os

SRC_GOLD  = "/opt/airflow/data/gold/openaq_15min"
SRC_SILVER= "/opt/airflow/data/silver/openaq"
OUT_DIR   = "/opt/airflow/exports"

CUTOFF_DAYS = 365
PM25_MIN, PM25_MAX = 0.0, 500.0 
TOP_N = 12
MIN_POINTS = 96  

def build_assets():
    import pandas as pd, numpy as np, os
    os.makedirs(OUT_DIR, exist_ok=True)

    g = pd.read_parquet(SRC_GOLD)
    g["window_start"] = pd.to_datetime(g["window_start"], utc=True)

    # lookback window + value clamp
    if len(g):
        cutoff = g["window_start"].max() - pd.Timedelta(days=CUTOFF_DAYS)
        g = g[g["window_start"] >= cutoff]
    g = g[g["pm25_avg"].between(PM25_MIN, PM25_MAX)]

    # helper columns
    g["date"] = g["window_start"].dt.date
    g["hour"] = g["window_start"].dt.hour
    g["dow"]  = g["window_start"].dt.day_name()

    def bucket(pm):
        if pd.isna(pm): return None
        if pm < 12: return "Good"
        if pm < 35.5: return "Moderate"
        if pm < 55.5: return "USG"
        if pm < 150.5: return "Unhealthy"
        if pm < 250.5: return "Very Unhealthy"
        return "Hazardous"

    # ---------- (1) 15-min timeseries ----------
    counts = g.groupby("location_id").size().sort_values(ascending=False)
    top = counts[counts >= MIN_POINTS].head(TOP_N).index
    if len(top) < TOP_N:  
        top = counts.head(TOP_N).index

    ts = g[g["location_id"].isin(top)].copy()
    ts["category"] = ts["pm25_avg"].apply(bucket)
    ts[["location_id","window_start","pm25_avg","samples","category","hour","dow","date"]]\
      .sort_values(["location_id","window_start"])\
      .to_csv(f"{OUT_DIR}/ts_15min.csv", index=False)

    # ---------- (2) daily aggregates + exceedance ----------
    daily = (g.groupby(["location_id","date"], as_index=False)
               .agg(pm25_daily_avg=("pm25_avg","mean"), intervals=("samples","sum")))
    daily["exceed_epa_35"] = (daily["pm25_daily_avg"] > 35).astype(int)
    daily["exceed_who_15"] = (daily["pm25_daily_avg"] > 15).astype(int)
    daily.to_csv(f"{OUT_DIR}/daily.csv", index=False)

    # ---------- (3) 24h smoothed latest map snapshot ----------
    s = pd.read_parquet(SRC_SILVER)
    ts_col = "ts_ts" if "ts_ts" in s.columns else "ts"
    s["ts_ts"] = pd.to_datetime(s[ts_col], errors="coerce", utc=True)
    s = s.dropna(subset=["ts_ts","lat","lon"])
    idx = s.groupby("location_id")["ts_ts"].idxmax()
    loc = s.loc[idx, ["location_id","lat","lon","ts_ts"]].rename(columns={"ts_ts":"last_seen"})

    if len(g):
        tmax = g["window_start"].max()
        g24 = g[(g["window_start"] >= tmax - pd.Timedelta(hours=24))]
        latest = (g24.groupby("location_id", as_index=False)
                    .agg(pm25_avg=("pm25_avg","median"),
                         latest_window=("window_start","max")))
    else:
        latest = g.groupby("location_id", as_index=False)\
                  .agg(pm25_avg=("pm25_avg","mean"),
                       latest_window=("window_start","max"))

    mp = loc.merge(latest, on="location_id", how="left")
    mp["category"] = mp["pm25_avg"].apply(bucket)
    mp.to_csv(f"{OUT_DIR}/latest_map.csv", index=False)

    # ---------- (4) 30-day exceedance leaderboard ----------
    if len(g):
        cutoff30 = g["window_start"].max() - pd.Timedelta(days=30)
        d30 = daily[daily["date"] >= cutoff30.date()]
    else:
        d30 = daily
    score = (d30.groupby("location_id", as_index=False)
             .agg(who_exceed_days=("exceed_who_15","sum"),
                  epa_exceed_days=("exceed_epa_35","sum"),
                  avg_pm25=("pm25_daily_avg","mean"),
                  days=("date","nunique"))
             .sort_values(["who_exceed_days","avg_pm25"], ascending=[False, False]))
    score.to_csv(f"{OUT_DIR}/exceedance_30d.csv", index=False)

with DAG(
    dag_id="export_openaq_dashboard_assets",
    start_date=datetime(2025,1,1),
    schedule_interval="@hourly",  
    catchup=False,
    default_args={"retries":1, "retry_delay": timedelta(minutes=2)},
    tags=["export","tableau","enrichment"],
):
    PythonOperator(task_id="build_assets", python_callable=build_assets)
