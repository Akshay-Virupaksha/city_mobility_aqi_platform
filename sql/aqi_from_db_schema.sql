--
-- PostgreSQL database dump
--

\restrict EN2QPFjmMcqDwEkc5J8QdfdoNfPhu6c6w1tWLh3oE6I5SRK72GSsQPJTAmtBh5E
-- Dumped from database version 15.2 (Debian 15.2-1.pgdg110+1)
-- Dumped by pg_dump version 15.2 (Debian 15.2-1.pgdg110+1)


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: openaq_15min; Type: TABLE; Schema: aqi; Owner: mobility
--

CREATE TABLE aqi.openaq_15min (
    location_id bigint NOT NULL,
    window_start timestamp with time zone NOT NULL,
    window_end timestamp with time zone NOT NULL,
    pm25_avg double precision,
    samples integer,
    loaded_at timestamp with time zone DEFAULT now()
);


ALTER TABLE aqi.openaq_15min OWNER TO mobility;

--
-- Name: daily_avg_mv; Type: MATERIALIZED VIEW; Schema: aqi; Owner: mobility
--

CREATE MATERIALIZED VIEW aqi.daily_avg_mv AS
 SELECT location_id,
    (date_trunc('day'::text, window_start))::date AS date,
    avg(pm25_avg) AS pm25_daily_avg,
    (sum(samples))::integer AS samples
   FROM aqi.openaq_15min
  GROUP BY location_id, ((date_trunc('day'::text, window_start))::date)
  WITH NO DATA;


ALTER MATERIALIZED VIEW aqi.daily_avg_mv OWNER TO mobility;

--
-- Name: exceedance_30d_mv; Type: MATERIALIZED VIEW; Schema: aqi; Owner: mobility
--

CREATE MATERIALIZED VIEW aqi.exceedance_30d_mv AS
 WITH recent AS (
         SELECT daily_avg_mv.location_id,
            daily_avg_mv.date,
            daily_avg_mv.pm25_daily_avg,
            daily_avg_mv.samples
           FROM aqi.daily_avg_mv
          WHERE (daily_avg_mv.date >= (CURRENT_DATE - 30))
        )
 SELECT location_id,
    sum(((pm25_daily_avg > (15)::double precision))::integer) AS who_exceed_days,
    sum(((pm25_daily_avg > (35)::double precision))::integer) AS epa_exceed_days,
    avg(pm25_daily_avg) AS avg_pm25_30d
   FROM recent
  GROUP BY location_id
  WITH NO DATA;


ALTER MATERIALIZED VIEW aqi.exceedance_30d_mv OWNER TO mobility;

--
-- Name: latest_15min_mv; Type: MATERIALIZED VIEW; Schema: aqi; Owner: mobility
--

CREATE MATERIALIZED VIEW aqi.latest_15min_mv AS
 SELECT DISTINCT ON (location_id) location_id,
    window_start AS last_seen,
    pm25_avg,
    samples
   FROM aqi.openaq_15min
  ORDER BY location_id, window_start DESC
  WITH NO DATA;


ALTER MATERIALIZED VIEW aqi.latest_15min_mv OWNER TO mobility;

--
-- Name: openaq_15min openaq_15min_pkey; Type: CONSTRAINT; Schema: aqi; Owner: mobility
--

ALTER TABLE ONLY aqi.openaq_15min
    ADD CONSTRAINT openaq_15min_pkey PRIMARY KEY (location_id, window_start);


--
-- Name: daily_avg_mv_pk; Type: INDEX; Schema: aqi; Owner: mobility
--

CREATE UNIQUE INDEX daily_avg_mv_pk ON aqi.daily_avg_mv USING btree (location_id, date);


--
-- Name: exceed_30d_mv_pk; Type: INDEX; Schema: aqi; Owner: mobility
--

CREATE UNIQUE INDEX exceed_30d_mv_pk ON aqi.exceedance_30d_mv USING btree (location_id);


--
-- Name: idx_openaq15_loc_time; Type: INDEX; Schema: aqi; Owner: mobility
--

CREATE INDEX idx_openaq15_loc_time ON aqi.openaq_15min USING btree (location_id, window_start);


--
-- Name: idx_openaq15_winstart; Type: INDEX; Schema: aqi; Owner: mobility
--

CREATE INDEX idx_openaq15_winstart ON aqi.openaq_15min USING btree (window_start);


--
-- Name: idx_openaq_15min_loc_ts; Type: INDEX; Schema: aqi; Owner: mobility
--

CREATE INDEX idx_openaq_15min_loc_ts ON aqi.openaq_15min USING btree (location_id, window_start);


--
-- Name: latest_15min_mv_pk; Type: INDEX; Schema: aqi; Owner: mobility
--

CREATE UNIQUE INDEX latest_15min_mv_pk ON aqi.latest_15min_mv USING btree (location_id);


--
-- PostgreSQL database dump complete
--

\unrestrict EN2QPFjmMcqDwEkc5J8QdfdoNfPhu6c6w1tWLh3oE6I5SRK72GSsQPJTAmtBh5E

