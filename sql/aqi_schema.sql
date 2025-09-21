CREATE SCHEMA IF NOT EXISTS aqi;

CREATE TABLE IF NOT EXISTS aqi.openaq_15min (
  location_id    BIGINT NOT NULL,
  window_start   TIMESTAMPTZ NOT NULL,
  window_end     TIMESTAMPTZ NOT NULL,
  pm25_avg       DOUBLE PRECISION,
  samples        INT,
  loaded_at      TIMESTAMPTZ DEFAULT NOW(),
  PRIMARY KEY (location_id, window_start)
);

CREATE INDEX IF NOT EXISTS idx_openaq15_winstart ON aqi.openaq_15min (window_start);
CREATE INDEX IF NOT EXISTS idx_openaq15_loc_time ON aqi.openaq_15min (location_id, window_start);

