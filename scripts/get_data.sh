#!/usr/bin/env bash
set -euo pipefail
OWNER="akshayin98"
REPO="city_mobility_aqi_platform"
TAG="v0.1.0"
ASSET=$(curl -sL "https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/${TAG}" \
  | python3 -c 'import sys,json;print([a["name"] for a in json.load(sys.stdin)["assets"] if "openaq_gold_exports" in a["name"]][0])')
mkdir -p data/gold airflow/dags/exports
echo "Downloading ${ASSET} ..."
curl -L -o /tmp/data.zip "https://github.com/${OWNER}/${REPO}/releases/download/${TAG}/${ASSET}"
unzip -o /tmp/data.zip -d .
echo "Done. Data under ./data/gold and ./airflow/dags/exports"
