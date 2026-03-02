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

announce_msg_file="$tmpdir/announce.msg"
health_msg_file="$tmpdir/health.msg"
version_file="$tmpdir/version.json"
permissions_file="$tmpdir/permissions.json"
manifest_file="$(cd "$(dirname "$0")/.." && pwd)/manifest.json"

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

echo "[validate] addon version API"
curl -fsS "${SERVICE_BASE_URL}/api/addon/version" > "$version_file"

echo "[validate] addon permissions API"
curl -fsS "${SERVICE_BASE_URL}/api/addon/permissions" > "$permissions_file"

if ! command -v mosquitto_sub >/dev/null 2>&1; then
  echo "[validate] ERROR: mosquitto_sub not installed"
  exit 1
fi

echo "[validate] mqtt announce topic"
mosquitto_sub "${sub_args[@]}" -F '%r\t%p' -t "${MQTT_BASE_TOPIC}/addons/mqtt/announce" > "$announce_msg_file"

echo "[validate] mqtt health topic"
mosquitto_sub "${sub_args[@]}" -F '%r\t%p' -t "${MQTT_BASE_TOPIC}/addons/mqtt/health" > "$health_msg_file"

python3 - "$announce_msg_file" "$health_msg_file" "$version_file" "$permissions_file" "$manifest_file" "$EXPECTED_ANNOUNCE_BASE_URL" <<'PY'
import json
import sys

announce_path, health_path, version_path, permissions_path, manifest_path, expected_base = sys.argv[1:7]
version_payload = json.load(open(version_path, "r", encoding="utf-8"))
permissions_payload = json.load(open(permissions_path, "r", encoding="utf-8"))
manifest = json.load(open(manifest_path, "r", encoding="utf-8"))

def parse_retained_message(path: str) -> tuple[bool, dict]:
    raw = open(path, "r", encoding="utf-8").read().strip()
    if "\t" not in raw:
        raise SystemExit(f"retained-format parse failed for {path}: {raw!r}")
    retained_text, payload_text = raw.split("\t", 1)
    return retained_text == "1", json.loads(payload_text)

announce_retained, announce = parse_retained_message(announce_path)
health_retained, health = parse_retained_message(health_path)

required_version_fields = {"addon_id", "version", "api_version", "manifest_version"}
missing_fields = required_version_fields.difference(version_payload.keys())
if missing_fields:
    raise SystemExit(f"version payload missing fields: {sorted(missing_fields)}")

if version_payload.get("addon_id") != manifest.get("id"):
    raise SystemExit(
        f"version addon_id mismatch: {version_payload.get('addon_id')} != {manifest.get('id')}"
    )
if version_payload.get("version") != manifest.get("version"):
    raise SystemExit(
        f"version payload mismatch: {version_payload.get('version')} != {manifest.get('version')}"
    )
if version_payload.get("manifest_version") != manifest.get("version"):
    raise SystemExit(
        "version manifest_version does not match manifest version"
    )

if not isinstance(permissions_payload, list):
    raise SystemExit("permissions payload must be an array")
manifest_permissions = manifest.get("permissions")
if permissions_payload != manifest_permissions:
    raise SystemExit(
        f"permissions mismatch: {permissions_payload} != {manifest_permissions}"
    )

if not announce_retained:
    raise SystemExit("announce topic is not retained")
if not health_retained:
    raise SystemExit("health topic is not retained")
if announce.get("base_url") != expected_base:
    raise SystemExit(f"announce base_url mismatch: {announce.get('base_url')} != {expected_base}")
if announce.get("id") != "mqtt":
    raise SystemExit(f"announce id mismatch: {announce.get('id')}")
if announce.get("addon_id") != version_payload.get("addon_id"):
    raise SystemExit("announce addon_id does not match version endpoint")
if announce.get("version") != version_payload.get("version"):
    raise SystemExit("announce version does not match version endpoint")
if announce.get("api_version") != version_payload.get("api_version"):
    raise SystemExit("announce api_version does not match version endpoint")
if announce.get("mode") != "standalone_service":
    raise SystemExit(f"announce mode mismatch: {announce.get('mode')}")
if health.get("status") not in {"healthy", "degraded", "offline"}:
    raise SystemExit(f"unexpected health status: {health.get('status')}")
if "last_seen" not in health:
    raise SystemExit("health payload missing last_seen")
print("api, announce, and health payload checks passed")
PY

if [[ -n "$CORE_PROXY_HEALTH_URL" ]]; then
  echo "[validate] core proxy health URL"
  curl -fsS "$CORE_PROXY_HEALTH_URL" >/dev/null
fi

echo "[validate] success"
