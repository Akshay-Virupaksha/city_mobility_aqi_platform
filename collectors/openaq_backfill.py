import os, sys, time, json, requests
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, parse_qs
from kafka import KafkaProducer

BASE = "https://api.openaq.org/v3"
API_KEY = os.getenv("OPENAQ_API_KEY")
PARAMETERS_ID = int(os.getenv("PARAMETERS_ID", "2"))  # 2 = PM2.5
FROM_ISO = os.getenv("FROM_ISO")
TO_ISO   = os.getenv("TO_ISO")
LIMIT = int(os.getenv("LIMIT", "1000"))              
MAX_LOCATIONS = int(os.getenv("MAX_LOCATIONS", "250"))
MAX_SENSORS_PER_LOC = int(os.getenv("MAX_SENSORS_PER_LOC", "20"))
BOOT = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("KAFKA_TOPIC", "openaq.measurements")

COUNTRY = os.getenv("COUNTRY")      
BBOX = os.getenv("BBOX")            

if not API_KEY:
    print("Missing OPENAQ_API_KEY", file=sys.stderr); sys.exit(1)

now = datetime.now(timezone.utc)
if not TO_ISO:
    TO_ISO = now.isoformat(timespec="seconds").replace("+00:00","Z")
if not FROM_ISO:
    FROM_ISO = (now - timedelta(days=365)).isoformat(timespec="seconds").replace("+00:00","Z")

headers = {"X-API-Key": API_KEY}

def http_get(url, params=None, max_retries=6):
    
    for i in range(max_retries):
        r = requests.get(url, headers=headers, params=params, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(min(2**i, 30)); continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()

def paginate(url, params):
    
    cursor = None
    while True:
        p = dict(params)
        if cursor: p["cursor"] = cursor
        data = http_get(url, p)
        yield data
        nxt = (data.get("links") or {}).get("next")
        if not nxt: break
        cursor = parse_qs(urlparse(nxt).query).get("cursor", [None])[0]

def list_locations():
    params = {"parameters_id": PARAMETERS_ID, "limit": 1000}
    if COUNTRY: params["iso"] = COUNTRY  
    if BBOX:    params["bbox"] = BBOX
    out = []
    for page in paginate(f"{BASE}/locations", params):
        out.extend(page.get("results", []))
        if len(out) >= MAX_LOCATIONS:
            break
    return out[:MAX_LOCATIONS]

def list_sensors_for_location(loc_id):
    params = {"limit": 1000, "parameters_id": PARAMETERS_ID}
    sensors = []
    for page in paginate(f"{BASE}/locations/{loc_id}/sensors", params):
        sensors.extend(page.get("results", []))
        if len(sensors) >= MAX_SENSORS_PER_LOC:
            break
    return sensors[:MAX_SENSORS_PER_LOC]

def backfill_sensor(sensor, loc_coords):
    sid = sensor["id"]
    coords = (sensor.get("coordinates") or {}) or (loc_coords or {})
    lat, lon = coords.get("latitude"), coords.get("longitude")

    params = {"date_from": FROM_ISO, "date_to": TO_ISO, "limit": LIMIT, "sort": "asc"}
    total = 0
    for page in paginate(f"{BASE}/sensors/{sid}/measurements", params):
        rows = page.get("results", [])
        if not rows: break
        for m in rows:
            when = m.get("datetime") or {}
            ts = when.get("utc") or when.get("local") or m.get("date")
            rec = {
                "source": "openaq",
                "parameter_id": m.get("parameters_id"),   # v3 returns parameters_id on measurements
                "sensor_id": sid,
                "location_id": sensor.get("locations_id") or sensor.get("location_id"),
                "value": m.get("value"),
                "lat": lat, "lon": lon,
                "ts": ts,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            producer.send(TOPIC, rec)
        producer.flush()
        total += len(rows)
    return total

producer = KafkaProducer(
    bootstrap_servers=BOOT,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    linger_ms=250, batch_size=32768, retries=5,
)

print(f"Backfill {FROM_ISO} → {TO_ISO} for PM2.5 (locations<= {MAX_LOCATIONS}, sensors/loc<= {MAX_SENSORS_PER_LOC})")

locs = list_locations()
print(f"Found {len(locs)} locations (parameters_id={PARAMETERS_ID}, country={COUNTRY or '-'}, bbox={BBOX or '-'})")

grand = 0
for i, loc in enumerate(locs, 1):
    coords = (loc.get("coordinates") or {})
    loc_id = loc["id"]
    sensors = list_sensors_for_location(loc_id)
    loc_total = 0
    for s in sensors:
        loc_total += backfill_sensor(s, coords)
    grand += loc_total
    print(f"[{i}/{len(locs)}] location {loc_id}: {len(sensors)} sensors → {loc_total} rows (cumulative {grand})")

print(f"Done. Produced total {grand} measurement rows to Kafka topic {TOPIC}.")
