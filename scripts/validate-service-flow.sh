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
AUTH_REQUIRED="${AUTH_REQUIRED:-0}"
JWT_SIGNING_KEY="${JWT_SIGNING_KEY:-}"
TOKEN_AUDIENCE="${TOKEN_AUDIENCE:-mqtt}"
POLICY_ENFORCEMENT="${POLICY_ENFORCEMENT:-0}"
POLICY_CONSUMER_ADDON_ID="${POLICY_CONSUMER_ADDON_ID:-validator-addon}"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

announce_msg_file="$tmpdir/announce.msg"
health_msg_file="$tmpdir/health.msg"
version_file="$tmpdir/version.json"
permissions_file="$tmpdir/permissions.json"
capabilities_file="$tmpdir/capabilities.json"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
manifest_file="$repo_root/manifest.json"

echo "[validate] local documentation/code alignment"
"$repo_root/scripts/check-doc-alignment.sh"

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

echo "[validate] addon capabilities API"
curl -fsS "${SERVICE_BASE_URL}/api/addon/capabilities" > "$capabilities_file"

if ! command -v mosquitto_sub >/dev/null 2>&1; then
  echo "[validate] ERROR: mosquitto_sub not installed"
  exit 1
fi
if [[ "$POLICY_ENFORCEMENT" == "1" ]] && ! command -v mosquitto_pub >/dev/null 2>&1; then
  echo "[validate] ERROR: mosquitto_pub not installed (required for POLICY_ENFORCEMENT=1)"
  exit 1
fi

echo "[validate] mqtt announce topic"
mosquitto_sub "${sub_args[@]}" -F '%r\t%p' -t "${MQTT_BASE_TOPIC}/addons/mqtt/announce" > "$announce_msg_file"

echo "[validate] mqtt health topic"
mosquitto_sub "${sub_args[@]}" -F '%r\t%p' -t "${MQTT_BASE_TOPIC}/addons/mqtt/health" > "$health_msg_file"

python3 - "$announce_msg_file" "$health_msg_file" "$version_file" "$permissions_file" "$capabilities_file" "$manifest_file" "$repo_root" "$EXPECTED_ANNOUNCE_BASE_URL" <<'PY'
import json
import re
import sys
from pathlib import Path

announce_path, health_path, version_path, permissions_path, capabilities_path, manifest_path, repo_root, expected_base = sys.argv[1:9]
version_payload = json.load(open(version_path, "r", encoding="utf-8"))
permissions_payload = json.load(open(permissions_path, "r", encoding="utf-8"))
capabilities_payload = json.load(open(capabilities_path, "r", encoding="utf-8"))
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
if not isinstance(manifest_permissions, list):
    raise SystemExit("manifest permissions must be an array")
if permissions_payload != manifest_permissions:
    raise SystemExit(
        f"permissions mismatch: {permissions_payload} != {manifest_permissions}"
    )

if manifest.get("package_profile") != "standalone_service":
    raise SystemExit(
        f"manifest package_profile mismatch: {manifest.get('package_profile')} != standalone_service"
    )

allowed_permissions = {
    "network.egress",
    "network.ingress",
    "mqtt.publish",
    "mqtt.subscribe",
}
undeclared_vocabulary = sorted(set(manifest_permissions) - allowed_permissions)
if undeclared_vocabulary:
    raise SystemExit(
        f"manifest contains non-canonical permissions: {undeclared_vocabulary}"
    )

permission_pattern = re.compile(r"\b(?:network\.(?:egress|ingress)|mqtt\.(?:publish|subscribe))\b")
used_permissions = set()
for source_file in list(Path(repo_root, "app").rglob("*.py")) + list(Path(repo_root, "scripts").rglob("*.sh")):
    source_text = source_file.read_text(encoding="utf-8")
    used_permissions.update(permission_pattern.findall(source_text))

undeclared_runtime_permissions = sorted(used_permissions - set(manifest_permissions))
if undeclared_runtime_permissions:
    raise SystemExit(
        f"undeclared permission literals found in source: {undeclared_runtime_permissions}"
    )

if not isinstance(capabilities_payload, list):
    raise SystemExit("capabilities payload must be an array")

announce_capabilities = announce.get("capabilities")
if not isinstance(announce_capabilities, list):
    raise SystemExit("announce capabilities must be an array")
if announce_capabilities != capabilities_payload:
    raise SystemExit(
        f"announce capabilities mismatch: {announce_capabilities} != {capabilities_payload}"
    )

capability_pattern = re.compile(r"^[a-z0-9]+(?:\.[a-z0-9]+)+$")
invalid_capabilities = [cap for cap in capabilities_payload if not capability_pattern.fullmatch(str(cap))]
if invalid_capabilities:
    raise SystemExit(
        f"invalid capability naming (expected dot-separated lowercase segments): {invalid_capabilities}"
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

python3 - "$repo_root" <<'PY'
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])

required_files = [
    repo_root / "app" / "services" / "token_auth.py",
    repo_root / "app" / "services" / "policy_cache.py",
    repo_root / "app" / "services" / "telemetry_reporter.py",
]
for file_path in required_files:
    if not file_path.exists():
        raise SystemExit(f"missing required contract file: {file_path}")

main_text = (repo_root / "app" / "main.py").read_text(encoding="utf-8")
mqtt_text = (repo_root / "app" / "services" / "mqtt_client.py").read_text(encoding="utf-8")
telemetry_text = (repo_root / "app" / "services" / "telemetry_reporter.py").read_text(encoding="utf-8")

required_markers = [
    ("token_validator", main_text),
    ("policy_cache", main_text),
    ("version=ADDON_VERSION.version", main_text),
    ("telemetry_reporter.start()", main_text),
    ("telemetry_reporter.stop()", main_text),
    ('"/api/telemetry/usage"', telemetry_text),
    ('"/policy/grants/"', mqtt_text),
    ('"/policy/revocations/"', mqtt_text),
]
for marker, text in required_markers:
    if marker not in text:
        raise SystemExit(f"missing contract marker: {marker}")

print("static contract wiring checks passed")
PY

create_token() {
  local subject="$1"
  local scope="$2"
  python3 - "$JWT_SIGNING_KEY" "$TOKEN_AUDIENCE" "$subject" "$scope" <<'PY'
import base64
import hashlib
import hmac
import json
import sys
import time

key, audience, subject, scope = sys.argv[1:5]
header = {"alg": "HS256", "typ": "JWT"}
payload = {
    "sub": subject,
    "aud": audience,
    "jti": f"validate-{int(time.time() * 1000)}",
    "exp": int(time.time()) + 300,
    "scp": [scope],
}
def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")
h = b64(json.dumps(header, separators=(",", ":")).encode("utf-8"))
p = b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
s = hmac.new(key.encode("utf-8"), f"{h}.{p}".encode("utf-8"), hashlib.sha256).digest()
print(f"{h}.{p}.{b64(s)}")
PY
}

if [[ "$AUTH_REQUIRED" == "1" ]]; then
  if [[ -z "$JWT_SIGNING_KEY" ]]; then
    echo "[validate] ERROR: JWT_SIGNING_KEY is required when AUTH_REQUIRED=1"
    exit 1
  fi

  echo "[validate] auth: unauthorized publish should return 401"
  auth_status="$(curl -sS -o "$tmpdir/auth_unauth.out" -w '%{http_code}' \
    -X POST "${SERVICE_BASE_URL}/api/mqtt/publish" \
    -H 'Content-Type: application/json' \
    -d '{"topic":"synthia/validate/auth","payload":{"ok":true},"retain":false,"qos":0}')"
  [[ "$auth_status" == "401" ]] || { echo "[validate] ERROR: expected 401, got ${auth_status}"; exit 1; }

  invalid_scope_token="$(create_token "$POLICY_CONSUMER_ADDON_ID" "telemetry.report")"
  echo "[validate] auth: wrong-scope publish should return 401"
  auth_scope_status="$(curl -sS -o "$tmpdir/auth_scope.out" -w '%{http_code}' \
    -X POST "${SERVICE_BASE_URL}/api/mqtt/publish" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${invalid_scope_token}" \
    -d '{"topic":"synthia/validate/auth-scope","payload":{"ok":true},"retain":false,"qos":0}')"
  [[ "$auth_scope_status" == "401" ]] || { echo "[validate] ERROR: expected 401, got ${auth_scope_status}"; exit 1; }

  valid_publish_token="$(create_token "$POLICY_CONSUMER_ADDON_ID" "mqtt.publish")"
  if [[ "$POLICY_ENFORCEMENT" != "1" ]]; then
    echo "[validate] auth: valid publish token should return 200"
    auth_ok_status="$(curl -sS -o "$tmpdir/auth_ok.out" -w '%{http_code}' \
      -X POST "${SERVICE_BASE_URL}/api/mqtt/publish" \
      -H 'Content-Type: application/json' \
      -H "Authorization: Bearer ${valid_publish_token}" \
      -d '{"topic":"synthia/validate/auth-ok","payload":{"ok":true},"retain":false,"qos":0}')"
    [[ "$auth_ok_status" == "200" ]] || { echo "[validate] ERROR: expected 200, got ${auth_ok_status}"; exit 1; }
  fi
fi

if [[ "$AUTH_REQUIRED" == "1" && "$POLICY_ENFORCEMENT" == "1" ]]; then
  valid_publish_token="${valid_publish_token:-$(create_token "$POLICY_CONSUMER_ADDON_ID" "mqtt.publish")}"

  grant_topic="${MQTT_BASE_TOPIC}/policy/grants/${POLICY_CONSUMER_ADDON_ID}"
  revoke_topic="${MQTT_BASE_TOPIC}/policy/revocations/${POLICY_CONSUMER_ADDON_ID}"

  grant_payload="$(python3 - "$POLICY_CONSUMER_ADDON_ID" <<'PY'
import json
import sys
consumer = sys.argv[1]
print(json.dumps({
    "grant_id": "validate-grant-1",
    "consumer_addon_id": consumer,
    "service": "mqtt",
    "status": "active",
    "scopes": ["mqtt.publish"],
}))
PY
)"

  echo "[validate] policy: publishing retained grant"
  mosquitto_pub "${sub_args[@]}" -r -t "$grant_topic" -m "$grant_payload"
  sleep 1

  policy_allow_status="$(curl -sS -o "$tmpdir/policy_allow.out" -w '%{http_code}' \
    -X POST "${SERVICE_BASE_URL}/api/mqtt/publish" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${valid_publish_token}" \
    -d '{"topic":"synthia/validate/policy-allow","payload":{"ok":true},"retain":false,"qos":0}')"
  [[ "$policy_allow_status" == "200" ]] || { echo "[validate] ERROR: expected 200 after grant, got ${policy_allow_status}"; exit 1; }

  revoke_payload="$(python3 - "$POLICY_CONSUMER_ADDON_ID" <<'PY'
import json
import sys
consumer = sys.argv[1]
print(json.dumps({"consumer_addon_id": consumer}))
PY
)"

  echo "[validate] policy: publishing retained revocation"
  mosquitto_pub "${sub_args[@]}" -r -t "$revoke_topic" -m "$revoke_payload"
  sleep 1

  policy_deny_status="$(curl -sS -o "$tmpdir/policy_deny.out" -w '%{http_code}' \
    -X POST "${SERVICE_BASE_URL}/api/mqtt/publish" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer ${valid_publish_token}" \
    -d '{"topic":"synthia/validate/policy-deny","payload":{"ok":true},"retain":false,"qos":0}')"
  [[ "$policy_deny_status" == "403" ]] || { echo "[validate] ERROR: expected 403 after revocation, got ${policy_deny_status}"; exit 1; }
fi

if [[ -n "$CORE_PROXY_HEALTH_URL" ]]; then
  echo "[validate] core proxy health URL"
  curl -fsS "$CORE_PROXY_HEALTH_URL" >/dev/null
fi

echo "[validate] success"
