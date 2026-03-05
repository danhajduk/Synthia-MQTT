#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-danhajduk/Synthia-MQTT}"
DEFAULT_INSTALL_DIR="${DEFAULT_INSTALL_DIR:-$HOME/SynthiaAddons/services/mqtt}"
DEFAULT_BASE_TOPIC="${DEFAULT_BASE_TOPIC:-synthia}"
DEFAULT_QOS="${DEFAULT_QOS:-1}"
DEFAULT_PORT="${DEFAULT_PORT:-18080}"

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-install.sh

Interactive installer that:
- downloads latest GitHub release addon.tgz
- installs into SSAP-style versions/current layout
- writes runtime .env
- optionally starts containers and registers with Core
EOF
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[bootstrap] ERROR: required command not found: $cmd" >&2
    exit 1
  fi
}

prompt_default() {
  local prompt="$1"
  local default_value="$2"
  local input
  read -r -p "$prompt [$default_value]: " input
  if [[ -z "$input" ]]; then
    echo "$default_value"
    return
  fi
  echo "$input"
}

prompt_yes_no() {
  local prompt="$1"
  local default_choice="$2"
  local suffix
  local reply

  if [[ "$default_choice" == "y" ]]; then
    suffix="[Y/n]"
  else
    suffix="[y/N]"
  fi

  while true; do
    read -r -p "$prompt $suffix: " reply
    reply="${reply,,}"
    if [[ -z "$reply" ]]; then
      reply="$default_choice"
    fi
    case "$reply" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

prompt_secret_optional() {
  local prompt="$1"
  local secret
  read -r -s -p "$prompt (leave blank if not needed): " secret
  echo
  echo "$secret"
}

json_extract_release() {
  local metadata_file="$1"
  python3 - "$metadata_file" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    data = json.load(handle)

tag = data.get("tag_name", "").strip()
assets = data.get("assets", [])

asset_url = ""
for asset in assets:
    if asset.get("name") == "addon.tgz":
        asset_url = asset.get("browser_download_url", "")
        break
if not asset_url:
    for asset in assets:
        name = str(asset.get("name", ""))
        if name.endswith(".tgz"):
            asset_url = asset.get("browser_download_url", "")
            break

if not tag:
    raise SystemExit("release metadata missing tag_name")
if not asset_url:
    raise SystemExit("release metadata missing addon .tgz asset")

print(tag)
print(asset_url)
PY
}

write_env_file() {
  local env_file="$1"
  cat > "$env_file" <<EOF
MQTT_HOST=${MQTT_HOST}
MQTT_PORT=${MQTT_PORT}
MQTT_CLIENT_ID=synthia-addon-mqtt
MQTT_BASE_TOPIC=${MQTT_BASE_TOPIC}
MQTT_QOS=${MQTT_QOS}
MQTT_TLS=${MQTT_TLS}
MQTT_USERNAME=${MQTT_USERNAME}
MQTT_PASSWORD=${MQTT_PASSWORD}
ANNOUNCE_BASE_URL=${ANNOUNCE_BASE_URL}
CORE_BASE_URL=${CORE_BASE_URL}
EOF
}

write_broker_override_compose() {
  local override_file="$1"
  cat > "$override_file" <<'EOF'
services:
  mosquitto:
    image: eclipse-mosquitto:2
    container_name: synthia-mosquitto
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro

  mqtt-addon:
    depends_on:
      - mosquitto
EOF
}

register_with_core() {
  local service_base="$1"
  local core_base="$2"
  local core_token="$3"
  local payload

  payload="$(printf '{"core_base_url":"%s","addon_id":"mqtt","base_url":"%s"%s}' \
    "$core_base" \
    "$service_base" \
    "$([[ -n "$core_token" ]] && printf ',\"auth_token\":\"%s\"' "$core_token")")"

  curl -fsS \
    -X POST "${service_base%/}/api/install/register-core" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null
}

main() {
  if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    usage
    return 0
  fi

  if [[ ! -t 0 ]]; then
    echo "[bootstrap] ERROR: interactive terminal required. Use --help for details." >&2
    return 1
  fi

  require_cmd curl
  require_cmd tar
  require_cmd python3

  echo "Synthia MQTT bootstrap installer"
  echo

  INSTALL_DIR="$(prompt_default "Install root directory" "$DEFAULT_INSTALL_DIR")"
  PUBLIC_HOST="$(prompt_default "Public hostname or IP for addon API" "localhost")"
  PUBLIC_PORT="$(prompt_default "Public HTTP port for addon API" "$DEFAULT_PORT")"
  ANNOUNCE_BASE_URL="$(prompt_default "Addon public base URL for announce/core" "http://${PUBLIC_HOST}:${PUBLIC_PORT}")"
  MQTT_BASE_TOPIC="$(prompt_default "MQTT base topic" "$DEFAULT_BASE_TOPIC")"
  MQTT_QOS="$(prompt_default "MQTT QoS (0,1,2)" "$DEFAULT_QOS")"

  if prompt_yes_no "Install local MQTT broker with Docker Compose override?" "n"; then
    INSTALL_LOCAL_BROKER="true"
    MQTT_HOST="mosquitto"
    MQTT_PORT="1883"
    MQTT_TLS="false"
    MQTT_USERNAME=""
    MQTT_PASSWORD=""
  else
    INSTALL_LOCAL_BROKER="false"
    MQTT_HOST="$(prompt_default "External MQTT host" "10.0.0.100")"
    MQTT_PORT="$(prompt_default "External MQTT port" "1883")"
    if prompt_yes_no "Enable MQTT TLS?" "n"; then
      MQTT_TLS="true"
    else
      MQTT_TLS="false"
    fi
    MQTT_USERNAME="$(prompt_default "MQTT username (blank allowed)" "")"
    MQTT_PASSWORD="$(prompt_secret_optional "MQTT password")"
  fi

  CORE_BASE_URL="$(prompt_default "Core host URL (blank to skip registration)" "")"
  REGISTER_WITH_CORE="false"
  CORE_ADMIN_TOKEN=""
  if [[ -n "$CORE_BASE_URL" ]]; then
    if prompt_yes_no "Register addon with Core after startup?" "y"; then
      REGISTER_WITH_CORE="true"
      CORE_ADMIN_TOKEN="$(prompt_secret_optional "Core admin bearer token")"
    fi
  fi

  START_SERVICES="false"
  if prompt_yes_no "Start addon service after install?" "y"; then
    START_SERVICES="true"
    require_cmd docker
  fi

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  metadata_file="$tmpdir/release.json"
  echo "[bootstrap] fetching latest release metadata from GitHub ($GITHUB_REPO)"
  curl -fsSL "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" -o "$metadata_file"

  mapfile -t release_info < <(json_extract_release "$metadata_file")
  tag_name="${release_info[0]}"
  asset_url="${release_info[1]}"
  version="${tag_name#v}"

  version_dir="$INSTALL_DIR/versions/$version"
  extract_dir="$version_dir/extracted"
  artifact_file="$version_dir/addon.tgz"
  mkdir -p "$version_dir"

  echo "[bootstrap] downloading ${asset_url}"
  curl -fsSL "$asset_url" -o "$artifact_file"

  rm -rf "$extract_dir"
  mkdir -p "$extract_dir"
  tar -xzf "$artifact_file" -C "$extract_dir"

  ln -sfn "versions/$version" "$INSTALL_DIR/current"

  active_root="$INSTALL_DIR/current/extracted"
  env_file="$active_root/.env"
  write_env_file "$env_file"
  echo "[bootstrap] wrote runtime env file: $env_file"

  compose_main="$active_root/docker/docker-compose.yml"
  compose_override="$active_root/docker/docker-compose.bootstrap.yml"

  if [[ "$INSTALL_LOCAL_BROKER" == "true" ]]; then
    write_broker_override_compose "$compose_override"
    echo "[bootstrap] wrote broker override compose: $compose_override"
  else
    rm -f "$compose_override"
  fi

  if [[ "$START_SERVICES" == "true" ]]; then
    echo "[bootstrap] starting containers"
    pushd "$active_root" >/dev/null
    if [[ "$INSTALL_LOCAL_BROKER" == "true" ]]; then
      docker compose -f "$compose_main" -f "$compose_override" up -d --remove-orphans
    else
      docker compose -f "$compose_main" up -d --remove-orphans
    fi
    popd >/dev/null
  fi

  if [[ "$REGISTER_WITH_CORE" == "true" ]]; then
    echo "[bootstrap] registering addon endpoint in Core"
    register_with_core "$ANNOUNCE_BASE_URL" "$CORE_BASE_URL" "$CORE_ADMIN_TOKEN"
  fi

  echo
  echo "[bootstrap] install complete"
  echo "[bootstrap] version: $version"
  echo "[bootstrap] install dir: $INSTALL_DIR"
  echo "[bootstrap] active root: $active_root"
  echo "[bootstrap] announce base URL: $ANNOUNCE_BASE_URL"
  if [[ "$INSTALL_LOCAL_BROKER" == "true" ]]; then
    echo "[bootstrap] mqtt broker: local docker service (mosquitto)"
  else
    echo "[bootstrap] mqtt broker: ${MQTT_HOST}:${MQTT_PORT} (tls=${MQTT_TLS})"
  fi
  if [[ "$REGISTER_WITH_CORE" == "true" ]]; then
    echo "[bootstrap] core registration: attempted via ${CORE_BASE_URL}"
  else
    echo "[bootstrap] core registration: skipped"
  fi
}

main "$@"
