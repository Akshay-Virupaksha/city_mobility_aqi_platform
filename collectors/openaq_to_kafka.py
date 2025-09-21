import os, json, time, requests
from datetime import datetime, timezone
from kafka import KafkaProducer

BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
TOPIC  = "openaq.measurements"

API_KEY = os.getenv("OPENAQ_API_KEY")
PARAM_ID = int(os.getenv("OPENAQ_PARAMETER_ID", "2"))  # default: PM2.5

def make_producer():
    return KafkaProducer(
        bootstrap_servers=BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=100, retries=5, acks="all",
    )

def fetch_latest(param_id: int, limit=500, max_pages=3):
    if not API_KEY:
        raise RuntimeError("Missing OPENAQ_API_KEY in environment")
    headers = {
        "X-API-Key": API_KEY,
        "User-Agent": "city-mobility-aqi-platform/1.0"
    }
    base = f"https://api.openaq.org/v3/parameters/{param_id}/latest"
    page = 1
    while page <= max_pages:
        resp = requests.get(base, params={"limit": limit, "page": page}, headers=headers, timeout=30)
        if resp.status_code == 401:
            raise RuntimeError("OpenAQ auth failed (401). Check OPENAQ_API_KEY.")
        if resp.status_code == 410:
            raise RuntimeError("OpenAQ v1/v2 retired. Use v3 endpoints.")
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        for r in results:
            yield r
        page += 1

def normalize(r, param_id: int):
    dt = (r.get("datetime") or {}).get("utc")
    coords = r.get("coordinates") or {}
    return {
        "source": "openaq",
        "parameter_id": param_id,        
        "sensor_id": r.get("sensorsId"),
        "location_id": r.get("locationsId"),
        "value": r.get("value"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "ts": dt,
        "ingested_at": datetime.now(timezone.utc).isoformat()
    }

def main():
    p = make_producer()
    while True:
        try:
            sent = 0
            for row in fetch_latest(PARAM_ID, limit=500, max_pages=2):
                msg = normalize(row, PARAM_ID)
                if msg["ts"] and msg["lat"] and msg["lon"]:
                    p.send(TOPIC, msg); sent += 1
            p.flush()
            print(f"v3 latest param={PARAM_ID} → sent {sent} events")
        except Exception as e:
            print("collector error:", e)
        time.sleep(60)  # poll every minute

if __name__ == "__main__":
    main()
