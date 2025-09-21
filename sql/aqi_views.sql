-- Daily averages
CREATE MATERIALIZED VIEW IF NOT EXISTS aqi.daily_avg_mv AS
SELECT
  location_id,
  date_trunc('day', window_start)::date AS date,
  AVG(pm25_avg)::float8  AS pm25_daily_avg,
  SUM(samples)::int      AS samples
FROM aqi.openaq_15min
GROUP BY 1,2;
CREATE UNIQUE INDEX IF NOT EXISTS daily_avg_mv_pk ON aqi.daily_avg_mv(location_id, date);

-- 30-day exceedances (WHO 15, EPA 35)
CREATE MATERIALIZED VIEW IF NOT EXISTS aqi.exceedance_30d_mv AS
WITH recent AS (
  SELECT * FROM aqi.daily_avg_mv
  WHERE date >= current_date - 30
)
SELECT
  location_id,
  SUM((pm25_daily_avg > 15)::int) AS who_exceed_days,
  SUM((pm25_daily_avg > 35)::int) AS epa_exceed_days,
  AVG(pm25_daily_avg)             AS avg_pm25_30d
FROM recent
GROUP BY 1;
CREATE UNIQUE INDEX IF NOT EXISTS exceed_30d_mv_pk ON aqi.exceedance_30d_mv(location_id);

-- Latest 15-min per location (for maps/QA)
CREATE MATERIALIZED VIEW IF NOT EXISTS aqi.latest_15min_mv AS
SELECT DISTINCT ON (location_id)
  location_id, window_start AS last_seen, pm25_avg, samples
FROM aqi.openaq_15min
ORDER BY location_id, window_start DESC;
CREATE UNIQUE INDEX IF NOT EXISTS latest_15min_mv_pk ON aqi.latest_15min_mv(location_id);
