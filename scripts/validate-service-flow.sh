#!/usr/bin/env bash
set -euo pipefail

SERVICE_BASE_URL="${SERVICE_BASE_URL:-http://localhost:18080}"
MQTT_HOST="${MQTT_HOST:-10.0.0.100}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_USERNAME="${MQTT_USERNAME:-}"
MQTT_PASSWORD="${MQTT_PASSWORD:-}"
MQTT_BASE_TOPIC="${MQTT_BASE_TOPIC:-synthia}"
EXPECTED_ANNOUNCE_BASE_URL="${EXPECTED_ANNOUNCE_BASE_URL:-$SERVICE_BASE_URL}"
CORE_PROXY_HEALTH_URL="${CORE_PROXY_HEALTH_URL:-}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

announce_file="$tmpdir/announce.json"
health_file="$tmpdir/health.json"

sub_args=(-h "$MQTT_HOST" -p "$MQTT_PORT" -W 20 -C 1)
if [[ -n "$MQTT_USERNAME" ]]; then
  sub_args+=(-u "$MQTT_USERNAME")
fi
if [[ -n "$MQTT_PASSWORD" ]]; then
  sub_args+=(-P "$MQTT_PASSWORD")
fi

echo "[validate] service healthz"
curl -fsS "${SERVICE_BASE_URL}/healthz" >/dev/null

echo "[validate] addon health API"
curl -fsS "${SERVICE_BASE_URL}/api/addon/health" > "$tmpdir/addon_health.json"

if ! command -v mosquitto_sub >/dev/null 2>&1; then
  echo "[validate] ERROR: mosquitto_sub not installed"
  exit 1
fi

echo "[validate] mqtt announce topic"
mosquitto_sub "${sub_args[@]}" -t "${MQTT_BASE_TOPIC}/addons/mqtt/announce" > "$announce_file"

echo "[validate] mqtt health topic"
mosquitto_sub "${sub_args[@]}" -t "${MQTT_BASE_TOPIC}/addons/mqtt/health" > "$health_file"

python3 - "$announce_file" "$health_file" "$EXPECTED_ANNOUNCE_BASE_URL" <<'PY'
import json
import sys

announce_path, health_path, expected_base = sys.argv[1:4]
announce = json.load(open(announce_path, "r", encoding="utf-8"))
health = json.load(open(health_path, "r", encoding="utf-8"))

if announce.get("base_url") != expected_base:
    raise SystemExit(f"announce base_url mismatch: {announce.get('base_url')} != {expected_base}")
if announce.get("id") != "mqtt":
    raise SystemExit(f"announce id mismatch: {announce.get('id')}")
if health.get("status") not in {"healthy", "degraded", "offline"}:
    raise SystemExit(f"unexpected health status: {health.get('status')}")
if "last_seen" not in health:
    raise SystemExit("health payload missing last_seen")
print("announce and health payload checks passed")
PY

if [[ -n "$CORE_PROXY_HEALTH_URL" ]]; then
  echo "[validate] core proxy health URL"
  curl -fsS "$CORE_PROXY_HEALTH_URL" >/dev/null
fi

echo "[validate] success"
