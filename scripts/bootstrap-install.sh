#!/usr/bin/env bash
set -euo pipefail

GITHUB_REPO="${GITHUB_REPO:-danhajduk/Synthia-MQTT}"
DEFAULT_INSTALL_DIR="${DEFAULT_INSTALL_DIR:-$PWD/SynthiaAddons/Synthia-MQTT}"
DEFAULT_BASE_TOPIC="${DEFAULT_BASE_TOPIC:-synthia}"
DEFAULT_QOS="${DEFAULT_QOS:-1}"
DEFAULT_PORT="${DEFAULT_PORT:-18080}"
REQUESTED_VERSION="latest"
FORCE_INSTALL="false"
ADDON_PORT="$DEFAULT_PORT"
BIND_HOST="${DEFAULT_BIND_HOST:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
if [[ -z "$BIND_HOST" ]]; then
  BIND_HOST="127.0.0.1"
fi
NO_OPEN="false"
TIMEOUT_SECONDS="60"
NON_INTERACTIVE="false"

usage() {
  cat <<'EOF'
Usage: ./scripts/bootstrap-install.sh [--version <tag|latest>] [--addon-port <port>] [--bind <host>] [--no-open] [--timeout-seconds <seconds>] [--non-interactive]

Interactive installer that:
- downloads latest GitHub release addon.tgz
- installs into SSAP-style versions/current layout
- writes runtime .env
- optionally starts containers and registers with Core

Options:
- --version <tag|latest>  Release tag to install (default: latest)
- --force                 Re-download/re-extract even if version is already installed
- --addon-port <port>     Host port to bind addon HTTP service to (default: 18080)
- --bind <host>           Host bind address for addon HTTP service (default: detected host IP)
- --no-open               Do not auto-open setup UI in browser
- --timeout-seconds <n>   Wait timeout for health endpoint readiness (default: 60)
- --non-interactive       Use defaults and skip prompts (for automation/validation)
- -h, --help              Show this help
EOF
}

die() {
  echo "[bootstrap] ERROR: $*" >&2
  exit 1
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

parse_release_metadata() {
  local metadata_file="$1"
  local preferred_tag="${2:-}"
  python3 - "$metadata_file" "$preferred_tag" <<'PY'
import json
import sys

path = sys.argv[1]
preferred_tag = sys.argv[2].strip()
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
if preferred_tag and tag != preferred_tag:
    raise SystemExit(f"release tag mismatch: expected {preferred_tag}, got {tag}")

print(tag)
print(asset_url)
PY
}

release_api_request() {
  local url="$1"
  local outfile="$2"
  local http_code
  if ! http_code="$(curl -sS -L -w '%{http_code}' -o "$outfile" "$url")"; then
    return 1
  fi
  echo "$http_code"
}

resolve_latest_release() {
  local tmpdir="$1"
  local metadata_file="$tmpdir/release-latest.json"
  local releases_html="$tmpdir/releases.html"
  local http_code

  echo "[bootstrap] resolving latest release via GitHub API" >&2
  if http_code="$(release_api_request "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" "$metadata_file")"; then
    if [[ "$http_code" == "200" ]]; then
      parse_release_metadata "$metadata_file"
      return 0
    fi
    echo "[bootstrap] GitHub API latest endpoint returned HTTP $http_code" >&2
  else
    echo "[bootstrap] GitHub API latest endpoint request failed" >&2
  fi

  echo "[bootstrap] falling back to GitHub Releases HTML parsing" >&2
  curl -fsSL "https://github.com/${GITHUB_REPO}/releases" -o "$releases_html" || \
    die "failed to fetch releases page fallback for ${GITHUB_REPO}"

  python3 - "$releases_html" "$GITHUB_REPO" <<'PY'
import re
import sys
from pathlib import Path

html = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
repo = sys.argv[2]
repo_re = re.escape(repo)

tag_match = re.search(rf'/{repo_re}/releases/tag/([^"?#/]+)', html)
if not tag_match:
    raise SystemExit("unable to resolve latest release tag from HTML")
tag = tag_match.group(1)

asset_matches = re.findall(rf'https://github\.com/{repo_re}/releases/download/{re.escape(tag)}/([^"?#]+)', html)
asset_name = ""
for candidate in asset_matches:
    if candidate == "addon.tgz":
        asset_name = candidate
        break
if not asset_name:
    for candidate in asset_matches:
        if candidate.endswith(".tgz"):
            asset_name = candidate
            break
if not asset_name:
    asset_name = "addon.tgz"

print(tag)
print(f"https://github.com/{repo}/releases/download/{tag}/{asset_name}")
PY
}

resolve_tag_release() {
  local requested_tag="$1"
  local tmpdir="$2"
  local normalized_tag="$requested_tag"
  local metadata_file="$tmpdir/release-tag.json"
  local http_code

  if [[ "$normalized_tag" != v* ]]; then
    normalized_tag="v${normalized_tag}"
  fi

  echo "[bootstrap] resolving release tag ${normalized_tag} via GitHub API" >&2
  if http_code="$(release_api_request "https://api.github.com/repos/${GITHUB_REPO}/releases/tags/${normalized_tag}" "$metadata_file")"; then
    if [[ "$http_code" == "200" ]]; then
      parse_release_metadata "$metadata_file" "$normalized_tag"
      return 0
    fi
    die "release tag ${normalized_tag} not found via GitHub API (HTTP ${http_code})"
  fi
  die "failed to resolve release tag ${normalized_tag} from GitHub API"
}

resolve_release() {
  local requested="$1"
  local tmpdir="$2"
  if [[ "$requested" == "latest" ]]; then
    resolve_latest_release "$tmpdir"
    return
  fi
  resolve_tag_release "$requested" "$tmpdir"
}

get_sha256() {
  local file_path="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$file_path" | awk '{print tolower($1)}'
    return
  fi
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$file_path" | awk '{print tolower($1)}'
    return
  fi
  die "sha256sum/shasum is required for checksum calculation"
}

discover_checksum_url() {
  local asset_url="$1"
  local base_url="${asset_url%/*}"
  local asset_name="${asset_url##*/}"
  local candidates=(
    "${asset_url}.sha256"
    "${base_url}/addon.tgz.sha256"
    "${base_url}/addon.sha256"
  )
  if [[ "$asset_name" == *.tgz ]]; then
    candidates+=("${base_url}/${asset_name%.tgz}.sha256")
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    if curl -fsSI "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

verify_or_print_checksum() {
  local artifact_file="$1"
  local checksum_url="$2"
  local tmpdir="$3"
  local actual_sha

  actual_sha="$(get_sha256 "$artifact_file")"
  if [[ -z "$checksum_url" ]]; then
    echo "[bootstrap] sha256 (computed): $actual_sha"
    return 0
  fi

  local checksum_file="$tmpdir/release.sha256"
  curl -fsSL "$checksum_url" -o "$checksum_file" || die "failed to download checksum file: $checksum_url"

  local expected_sha
  expected_sha="$(awk '{for (i = 1; i <= NF; i++) if ($i ~ /^[A-Fa-f0-9]{64}$/) {print tolower($i); exit}}' "$checksum_file")"
  [[ -n "$expected_sha" ]] || die "checksum file did not contain a SHA256 digest: $checksum_url"

  if [[ "$expected_sha" != "$actual_sha" ]]; then
    die "sha256 mismatch for downloaded artifact (expected ${expected_sha}, got ${actual_sha})"
  fi
  echo "[bootstrap] sha256 verified: $actual_sha"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)
        shift
        [[ $# -gt 0 ]] || die "--version requires a value"
        REQUESTED_VERSION="$1"
        ;;
      --force)
        FORCE_INSTALL="true"
        ;;
      --addon-port)
        shift
        [[ $# -gt 0 ]] || die "--addon-port requires a value"
        [[ "$1" =~ ^[0-9]+$ ]] || die "--addon-port must be numeric"
        (( "$1" >= 1 && "$1" <= 65535 )) || die "--addon-port must be between 1 and 65535"
        ADDON_PORT="$1"
        ;;
      --bind)
        shift
        [[ $# -gt 0 ]] || die "--bind requires a value"
        BIND_HOST="$1"
        ;;
      --no-open)
        NO_OPEN="true"
        ;;
      --timeout-seconds)
        shift
        [[ $# -gt 0 ]] || die "--timeout-seconds requires a value"
        [[ "$1" =~ ^[0-9]+$ ]] || die "--timeout-seconds must be numeric"
        (( "$1" >= 1 )) || die "--timeout-seconds must be >= 1"
        TIMEOUT_SECONDS="$1"
        ;;
      --non-interactive)
        NON_INTERACTIVE="true"
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "unknown option: $1"
        ;;
    esac
    shift
  done
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

write_addon_port_override_compose() {
  local override_file="$1"
  local compose_bind_host="$BIND_HOST"
  if [[ "$compose_bind_host" == "localhost" ]]; then
    compose_bind_host="127.0.0.1"
  fi
  cat > "$override_file" <<EOF
services:
  mqtt-addon:
    ports:
      - "${compose_bind_host}:${ADDON_PORT}:8080"
EOF
}

resolve_addon_id() {
  local manifest_path="$1"
  python3 - "$manifest_path" <<'PY'
import json
import sys

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

addon_id = str(manifest.get("id", "")).strip()
if not addon_id:
    raise SystemExit("manifest id is missing")
print(addon_id)
PY
}

ensure_services_symlink() {
  local services_root="$1"
  local addon_id="$2"
  local install_dir="$3"
  local services_link="$services_root/$addon_id"

  mkdir -p "$services_root"

  if [[ -e "$services_link" && ! -L "$services_link" ]]; then
    die "services link target already exists and is not a symlink: $services_link"
  fi

  ln -sfn "$install_dir" "$services_link"
  echo "[bootstrap] ensured services symlink: $services_link -> $install_dir"
}

resolve_publisher_key_id() {
  local manifest_path="$1"
  python3 - "$manifest_path" <<'PY'
import json
import sys

manifest_path = sys.argv[1]
with open(manifest_path, "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

publisher = manifest.get("publisher") or {}
publisher_id = str(publisher.get("id", "")).strip()
if not publisher_id:
    publisher_id = "publisher.unknown"
if "#" not in publisher_id:
    publisher_id = f"{publisher_id}#ed25519"
print(publisher_id)
PY
}

discover_signature_url() {
  local asset_url="$1"
  local base_url="${asset_url%/*}"
  local asset_name="${asset_url##*/}"
  local candidates=(
    "${base_url}/addon.release_sig.b64"
    "${asset_url}.release_sig.b64"
  )
  if [[ "$asset_name" == *.tgz ]]; then
    candidates+=("${base_url}/${asset_name%.tgz}.release_sig.b64")
  fi

  local candidate
  for candidate in "${candidates[@]}"; do
    if curl -fsSI "$candidate" >/dev/null 2>&1; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

resolve_signature_value() {
  local signature_url="${1:-}"
  local tmpdir="$2"
  local signature_file="$tmpdir/release.sig.b64"
  local signature_value=""

  if [[ -n "$signature_url" ]]; then
    if curl -fsSL "$signature_url" -o "$signature_file"; then
      signature_value="$(tr -d ' \t\r\n' < "$signature_file")"
    fi
  fi

  if [[ -z "$signature_value" ]]; then
    signature_value="BASE64_SIGNATURE"
  fi

  echo "$signature_value"
}

write_desired_file() {
  local desired_file="$1"
  local addon_id="$2"
  local version="$3"
  local artifact_url="$4"
  local artifact_sha="$5"
  local publisher_key_id="$6"
  local signature_value="$7"
  local core_url="$8"
  local project_name="$9"
  local host_port="${10}"

  cat > "$desired_file" <<EOF
{
  "ssap_version": "1.0",
  "addon_id": "${addon_id}",
  "mode": "standalone_service",
  "desired_state": "running",
  "channel": "stable",
  "pinned_version": "${version}",
  "install_source": {
    "type": "catalog",
    "catalog_id": "official",
    "release": {
      "artifact_url": "${artifact_url}",
      "sha256": "${artifact_sha}",
      "publisher_key_id": "${publisher_key_id}",
      "signature": {
        "type": "ed25519",
        "value": "${signature_value}"
      }
    }
  },
  "runtime": {
    "orchestrator": "docker_compose",
    "project_name": "${project_name}",
    "network": "synthia_net",
    "ports": [
      {
        "host": ${host_port},
        "container": 8080,
        "proto": "tcp",
        "purpose": "http_api"
      }
    ],
    "bind_localhost": true
  },
  "config": {
    "env": {
      "CORE_URL": "${core_url}",
      "SYNTHIA_ADDON_ID": "${addon_id}",
      "SYNTHIA_SERVICE_TOKEN": "\${SYNTHIA_SERVICE_TOKEN}"
    }
  }
}
EOF
}

wait_for_health() {
  local health_url="$1"
  local timeout_seconds="$2"
  local elapsed=0
  local interval=2

  echo "[bootstrap] waiting for health endpoint: $health_url (timeout=${timeout_seconds}s)"
  while (( elapsed < timeout_seconds )); do
    if curl -fsS "$health_url" >/dev/null 2>&1; then
      echo "[bootstrap] health endpoint is ready after ${elapsed}s"
      return 0
    fi
    echo "[bootstrap] health not ready yet (${elapsed}s elapsed)"
    sleep "$interval"
    (( elapsed += interval ))
  done
  return 1
}

open_browser_url() {
  local url="$1"

  if [[ "$NO_OPEN" == "true" ]]; then
    echo "[bootstrap] --no-open set, not opening browser"
    echo "[bootstrap] setup UI: $url"
    return 0
  fi

  if command -v xdg-open >/dev/null 2>&1; then
    if xdg-open "$url" >/dev/null 2>&1; then
      echo "[bootstrap] opened setup UI via xdg-open: $url"
      return 0
    fi
  fi
  if command -v open >/dev/null 2>&1; then
    if open "$url" >/dev/null 2>&1; then
      echo "[bootstrap] opened setup UI via open: $url"
      return 0
    fi
  fi

  echo "[bootstrap] browser opener not available or failed"
  echo "[bootstrap] setup UI: $url"
  return 0
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
  parse_args "$@"

  if [[ "$NON_INTERACTIVE" != "true" && ! -t 0 ]]; then
    echo "[bootstrap] ERROR: interactive terminal required. Use --help for details." >&2
    return 1
  fi

  require_cmd curl
  require_cmd tar
  require_cmd python3

  echo "Synthia MQTT bootstrap installer"
  echo

  if [[ "$NON_INTERACTIVE" == "true" ]]; then
    echo "[bootstrap] non-interactive mode enabled (using defaults)"
    INSTALL_DIR="$DEFAULT_INSTALL_DIR"
    PUBLIC_HOST="$BIND_HOST"
    PUBLIC_PORT="$ADDON_PORT"
    ANNOUNCE_BASE_URL="http://${PUBLIC_HOST}:${PUBLIC_PORT}"
    MQTT_BASE_TOPIC="$DEFAULT_BASE_TOPIC"
    MQTT_QOS="$DEFAULT_QOS"

    INSTALL_LOCAL_BROKER="false"
    MQTT_HOST="10.0.0.100"
    MQTT_PORT="1883"
    MQTT_TLS="false"
    MQTT_USERNAME=""
    MQTT_PASSWORD=""

    CORE_BASE_URL=""
    REGISTER_WITH_CORE="false"
    CORE_ADMIN_TOKEN=""
    START_SERVICES="true"
  else
    INSTALL_DIR="$(prompt_default "Install root directory" "$DEFAULT_INSTALL_DIR")"
    PUBLIC_HOST="$(prompt_default "Public hostname or IP for addon API" "$BIND_HOST")"
    PUBLIC_PORT="$(prompt_default "Public HTTP port for addon API" "$ADDON_PORT")"
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
    fi
  fi

  if [[ "$PUBLIC_HOST" == "localhost" || "$PUBLIC_HOST" == "127.0.0.1" ]]; then
    PUBLIC_HOST="$BIND_HOST"
  fi

  if [[ "$START_SERVICES" == "true" ]]; then
    require_cmd docker
  fi

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  mapfile -t release_info < <(resolve_release "$REQUESTED_VERSION" "$tmpdir")
  [[ "${#release_info[@]}" -ge 2 ]] || die "failed to resolve release metadata for version=${REQUESTED_VERSION}"
  tag_name="${release_info[0]}"
  asset_url="${release_info[1]}"
  version="${tag_name#v}"
  echo "[bootstrap] resolved release tag: $tag_name"
  echo "[bootstrap] resolved artifact url: $asset_url"

  checksum_url=""
  if checksum_url="$(discover_checksum_url "$asset_url")"; then
    echo "[bootstrap] checksum source: $checksum_url"
  else
    echo "[bootstrap] checksum source: none found (will compute local SHA256)"
    checksum_url=""
  fi

  version_dir="$INSTALL_DIR/versions/$version"
  extract_dir="$version_dir/extracted"
  artifact_file="$version_dir/addon.tgz"
  current_link="$INSTALL_DIR/current"
  requested_link_target="versions/$version"
  current_link_target=""

  mkdir -p "$INSTALL_DIR/versions"
  if [[ -L "$current_link" ]]; then
    current_link_target="$(readlink "$current_link" || true)"
  fi

  artifact_exists="false"
  extract_exists="false"
  if [[ -f "$artifact_file" ]]; then
    artifact_exists="true"
  fi
  if [[ -d "$extract_dir" ]]; then
    extract_exists="true"
  fi

  need_download="true"
  need_extract="true"
  if [[ "$FORCE_INSTALL" != "true" ]]; then
    if [[ "$artifact_exists" == "true" ]]; then
      need_download="false"
      echo "[bootstrap] artifact already present, skipping download (use --force to re-download)"
    fi
    if [[ "$extract_exists" == "true" ]]; then
      need_extract="false"
      echo "[bootstrap] extracted version already present, skipping extract (use --force to re-extract)"
    fi
    if [[ "$current_link_target" == "$requested_link_target" && "$need_download" == "false" && "$need_extract" == "false" ]]; then
      echo "[bootstrap] current already points to requested version and install artifacts are present"
    fi
  fi

  mkdir -p "$version_dir"

  if [[ "$need_download" == "true" ]]; then
    echo "[bootstrap] downloading ${asset_url}"
    curl -fsSL "$asset_url" -o "$artifact_file"
    verify_or_print_checksum "$artifact_file" "$checksum_url" "$tmpdir"
  else
    verify_or_print_checksum "$artifact_file" "" "$tmpdir"
  fi

  if [[ "$need_extract" == "true" ]]; then
    rm -rf "$extract_dir"
    mkdir -p "$extract_dir"
    tar -xzf "$artifact_file" -C "$extract_dir"
  fi

  if [[ "$current_link_target" != "$requested_link_target" ]]; then
    ln -sfn "$requested_link_target" "$current_link"
    echo "[bootstrap] updated current symlink -> $requested_link_target"
  else
    echo "[bootstrap] current symlink already points to $requested_link_target"
  fi

  active_root="$INSTALL_DIR/current/extracted"
  manifest_file="$active_root/manifest.json"
  addon_id="$(resolve_addon_id "$manifest_file")"
  services_root="$PWD/SynthiaAddons/services"
  ensure_services_symlink "$services_root" "$addon_id" "$INSTALL_DIR"

  artifact_sha="$(get_sha256 "$artifact_file")"
  publisher_key_id="$(resolve_publisher_key_id "$manifest_file")"
  signature_url=""
  if signature_url="$(discover_signature_url "$asset_url")"; then
    echo "[bootstrap] signature source: $signature_url"
  else
    echo "[bootstrap] signature source: none found (using placeholder value)"
    signature_url=""
  fi
  signature_value="$(resolve_signature_value "$signature_url" "$tmpdir")"
  desired_core_url="${CORE_BASE_URL:-http://127.0.0.1:8000}"
  desired_project_name="synthia-addon-${addon_id}"
  desired_file="$INSTALL_DIR/desired.json"
  write_desired_file \
    "$desired_file" \
    "$addon_id" \
    "$version" \
    "$asset_url" \
    "$artifact_sha" \
    "$publisher_key_id" \
    "$signature_value" \
    "$desired_core_url" \
    "$desired_project_name" \
    "$ADDON_PORT"
  echo "[bootstrap] wrote desired file: $desired_file"

  env_file="$active_root/.env"
  write_env_file "$env_file"
  echo "[bootstrap] wrote runtime env file: $env_file"

  compose_main="$active_root/docker/docker-compose.yml"
  compose_override="$active_root/docker/docker-compose.bootstrap.yml"
  compose_port_override="$active_root/docker/docker-compose.port-override.yml"
  write_addon_port_override_compose "$compose_port_override"

  if [[ "$INSTALL_LOCAL_BROKER" == "true" ]]; then
    write_broker_override_compose "$compose_override"
    echo "[bootstrap] wrote broker override compose: $compose_override"
    echo "[bootstrap] note: bootstrap startup uses addon-only mode and does not start broker containers"
  else
    rm -f "$compose_override"
  fi

  if [[ "$START_SERVICES" == "true" ]]; then
    echo "[bootstrap] starting addon-only container"
    pushd "$active_root" >/dev/null
    docker compose -f "$compose_main" -f "$compose_port_override" up -d --remove-orphans --no-deps mqtt-addon
    popd >/dev/null

    service_base_url="http://${BIND_HOST}:${ADDON_PORT}"
    health_url="${service_base_url}/healthz"
    ui_url="http://${PUBLIC_HOST}:${ADDON_PORT}/ui"

    if wait_for_health "$health_url" "$TIMEOUT_SECONDS"; then
      open_browser_url "$ui_url"
    else
      die "health endpoint did not become ready within ${TIMEOUT_SECONDS}s at ${health_url}"
    fi
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
