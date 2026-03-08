#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Synthia MQTT artifact bootstrap
#
# Creates:
#   ./SynthiaAddons/services/mqtt/
#   ./SynthiaAddons/services/mqtt/versions/<version>/addon.tgz
#   ./SynthiaAddons/services/mqtt/versions/<version>/extracted/*
#   ./SynthiaAddons/services/mqtt/desired.json
#   ./SynthiaAddons/services/mqtt/runtime.json
#   ./SynthiaAddons/Synthia-MQTT -> ./SynthiaAddons/services/mqtt (compatibility)
#
# Usage:
#   ./bootstrap-artifact.sh
#   ./bootstrap-artifact.sh --version latest
#   ./bootstrap-artifact.sh --version <tag>
#   ./bootstrap-artifact.sh --version v<major.minor.patch>
#   ./bootstrap-artifact.sh --core-url http://10.0.0.100:9001
# ------------------------------------------------------------

GITHUB_REPO="${GITHUB_REPO:-danhajduk/Synthia-MQTT}"
ADDON_ID="mqtt"
ADDON_NAME="Synthia MQTT"
ADDONS_ROOT="${ADDONS_ROOT:-./SynthiaAddons}"
SERVICES_ROOT="${SERVICES_ROOT:-${ADDONS_ROOT}/services}"
INSTALL_ROOT="${INSTALL_ROOT:-${SERVICES_ROOT}/${ADDON_ID}}"
LEGACY_ROOT="${LEGACY_ROOT:-${ADDONS_ROOT}/Synthia-MQTT}"
CATALOG_ID="${CATALOG_ID:-official}"
CHANNEL="${CHANNEL:-stable}"
MODE="${MODE:-standalone_service}"
DESIRED_STATE="${DESIRED_STATE:-running}"
REQUESTED_VERSION="latest"
CORE_URL="${CORE_URL:-http://127.0.0.1:9001}"
PROJECT_NAME="${PROJECT_NAME:-synthia-addon-mqtt}"

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --version <latest|tag>   Version to install (default: latest)
  --core-url <url>         Core URL to place into desired.json
  --install-root <path>    Install root (default: ./SynthiaAddons/services/mqtt)
  --services-root <path>   Services root (default: ./SynthiaAddons/services)
  --legacy-root <path>     Legacy compatibility root symlink (default: ./SynthiaAddons/Synthia-MQTT)
  -h, --help               Show this help

Examples:
  $0
  $0 --version latest
  $0 --version v<major.minor.patch>
  $0 --version <major.minor.patch> --core-url http://10.0.0.100:9001
EOF
}

die() {
  echo "[bootstrap] ERROR: $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found: $1"
}

extract_compose_file() {
  local artifact_file="$1"
  local compose_file="$2"

  if tar -tzf "$artifact_file" ./docker/docker-compose.yml >/dev/null 2>&1; then
    tar -xOf "$artifact_file" ./docker/docker-compose.yml > "$compose_file"
    return
  fi

  if tar -tzf "$artifact_file" docker/docker-compose.yml >/dev/null 2>&1; then
    tar -xOf "$artifact_file" docker/docker-compose.yml > "$compose_file"
    return
  fi

  die "artifact missing docker/docker-compose.yml"
}

extract_artifact_tree() {
  local artifact_file="$1"
  local extracted_dir="$2"

  rm -rf "$extracted_dir"
  mkdir -p "$extracted_dir"
  tar -xzf "$artifact_file" -C "$extracted_dir"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)
        shift
        [[ $# -gt 0 ]] || die "--version requires a value"
        REQUESTED_VERSION="$1"
        ;;
      --core-url)
        shift
        [[ $# -gt 0 ]] || die "--core-url requires a value"
        CORE_URL="$1"
        ;;
      --install-root)
        shift
        [[ $# -gt 0 ]] || die "--install-root requires a value"
        INSTALL_ROOT="$1"
        ;;
      --services-root)
        shift
        [[ $# -gt 0 ]] || die "--services-root requires a value"
        SERVICES_ROOT="$1"
        ;;
      --legacy-root)
        shift
        [[ $# -gt 0 ]] || die "--legacy-root requires a value"
        LEGACY_ROOT="$1"
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

release_api_request() {
  local url="$1"
  local outfile="$2"
  local http_code
  http_code="$(curl -sS -L -w '%{http_code}' -o "$outfile" "$url")" || return 1
  echo "$http_code"
}

parse_release_metadata() {
  local metadata_file="$1"
  local preferred_tag="${2:-}"

  python3 - "$metadata_file" "$preferred_tag" <<'PY'
import json
import sys

path = sys.argv[1]
preferred = sys.argv[2].strip()

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

tag = str(data.get("tag_name", "")).strip()
if not tag:
    raise SystemExit("release metadata missing tag_name")

assets = data.get("assets", []) or []
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

if not asset_url:
    raise SystemExit("release metadata missing addon.tgz asset")

if preferred and tag != preferred:
    raise SystemExit(f"release tag mismatch: expected {preferred}, got {tag}")

print(tag)
print(asset_url)
PY
}

resolve_latest_release() {
  local tmpdir="$1"
  local metadata_file="$tmpdir/release-latest.json"
  local http_code

  echo "[bootstrap] resolving latest release from GitHub API" >&2
  http_code="$(release_api_request "https://api.github.com/repos/${GITHUB_REPO}/releases/latest" "$metadata_file")" \
    || die "failed to query GitHub latest release API"

  [[ "$http_code" == "200" ]] || die "GitHub latest release API returned HTTP $http_code"

  parse_release_metadata "$metadata_file"
}

resolve_tag_release() {
  local requested_tag="$1"
  local tmpdir="$2"
  local normalized_tag="$requested_tag"
  local metadata_file="$tmpdir/release-tag.json"
  local http_code

  [[ "$normalized_tag" == v* ]] || normalized_tag="v${normalized_tag}"

  echo "[bootstrap] resolving tag ${normalized_tag} from GitHub API" >&2
  http_code="$(release_api_request "https://api.github.com/repos/${GITHUB_REPO}/releases/tags/${normalized_tag}" "$metadata_file")" \
    || die "failed to query GitHub tag release API"

  [[ "$http_code" == "200" ]] || die "GitHub tag release API returned HTTP $http_code for ${normalized_tag}"

  parse_release_metadata "$metadata_file" "$normalized_tag"
}

resolve_release() {
  local requested="$1"
  local tmpdir="$2"

  if [[ "$requested" == "latest" ]]; then
    resolve_latest_release "$tmpdir"
  else
    resolve_tag_release "$requested" "$tmpdir"
  fi
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

  die "sha256sum or shasum is required"
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

  if [[ -n "$signature_url" ]]; then
    curl -fsSL "$signature_url" -o "$signature_file" || die "failed to download signature file: $signature_url"
    tr -d ' \t\r\n' < "$signature_file"
    return
  fi

  echo "BASE64_SIGNATURE"
}

write_desired_json() {
  local file_path="$1"
  local version="$2"
  local artifact_url="$3"
  local artifact_sha="$4"
  local signature_value="$5"

  cat > "$file_path" <<EOF
{
  "ssap_version": "1.0",
  "addon_id": "${ADDON_ID}",
  "mode": "${MODE}",
  "desired_state": "${DESIRED_STATE}",
  "channel": "${CHANNEL}",
  "pinned_version": "${version}",
  "install_source": {
    "type": "catalog",
    "catalog_id": "${CATALOG_ID}",
    "release": {
      "artifact_url": "${artifact_url}",
      "sha256": "${artifact_sha}",
      "publisher_key_id": "publisher.danhajduk#ed25519",
      "signature": {
        "type": "ed25519",
        "value": "${signature_value}"
      }
    }
  },
  "runtime": {
    "orchestrator": "docker_compose",
    "project_name": "${PROJECT_NAME}",
    "network": "synthia_net"
  },
  "config": {
    "env": {
      "CORE_URL": "${CORE_URL}",
      "SYNTHIA_ADDON_ID": "${ADDON_ID}",
      "SYNTHIA_SERVICE_TOKEN": "\${SYNTHIA_SERVICE_TOKEN}"
    }
  }
}
EOF
}

write_runtime_json() {
  local file_path="$1"
  local version="$2"
  local compose_file="$3"

  cat > "$file_path" <<EOF
{
  "ssap_version": "1.0",
  "addon_id": "${ADDON_ID}",
  "active_version": "${version}",
  "state": "installed",
  "last_action": {
    "type": "bootstrap_install",
    "ok": true
  },
  "docker": {
    "project_name": "${PROJECT_NAME}",
    "compose_file": "${compose_file}"
  }
}
EOF
}

main() {
  parse_args "$@"

  require_cmd curl
  require_cmd python3
  require_cmd tar

  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "'"${tmpdir}"'"' EXIT

  mapfile -t release_info < <(resolve_release "$REQUESTED_VERSION" "$tmpdir")
  [[ "${#release_info[@]}" -ge 2 ]] || die "failed to resolve release metadata"

  local tag_name="${release_info[0]}"
  local asset_url="${release_info[1]}"
  local version="${tag_name#v}"

  local version_dir="${INSTALL_ROOT}/versions/${version}"
  local artifact_file="${version_dir}/addon.tgz"
  local compose_file="${version_dir}/docker-compose.yml"
  local extracted_dir="${version_dir}/extracted"
  local desired_file="${INSTALL_ROOT}/desired.json"
  local runtime_file="${INSTALL_ROOT}/runtime.json"
  local current_link="${INSTALL_ROOT}/current"
  local compatibility_link="${LEGACY_ROOT}"

  echo "[bootstrap] release tag: ${tag_name}"
  echo "[bootstrap] version: ${version}"
  echo "[bootstrap] asset url: ${asset_url}"

  mkdir -p "${version_dir}"
  mkdir -p "${SERVICES_ROOT}"
  mkdir -p "${INSTALL_ROOT}"

  echo "[bootstrap] downloading artifact -> ${artifact_file}"
  curl -fsSL "${asset_url}" -o "${artifact_file}"

  local artifact_sha
  artifact_sha="$(get_sha256 "${artifact_file}")"
  echo "[bootstrap] sha256: ${artifact_sha}"

  echo "[bootstrap] extracting compose file -> ${compose_file}"
  extract_compose_file "${artifact_file}" "${compose_file}"

  echo "[bootstrap] extracting artifact build context -> ${extracted_dir}"
  extract_artifact_tree "${artifact_file}" "${extracted_dir}"

  local signature_url=""
  if signature_url="$(discover_signature_url "${asset_url}")"; then
    echo "[bootstrap] signature url: ${signature_url}"
  else
    echo "[bootstrap] signature url: not found, using placeholder"
    signature_url=""
  fi

  local signature_value
  signature_value="$(resolve_signature_value "${signature_url}" "$tmpdir")"

  echo "[bootstrap] writing desired.json -> ${desired_file}"
  write_desired_json "${desired_file}" "${version}" "${asset_url}" "${artifact_sha}" "${signature_value}"

  echo "[bootstrap] writing runtime.json -> ${runtime_file}"
  write_runtime_json "${runtime_file}" "${version}" "${compose_file}"

  echo "[bootstrap] updating current symlink -> versions/${version}"
  ln -sfn "versions/${version}" "${current_link}"

  echo "[bootstrap] updating compatibility symlink -> ${compatibility_link}"
  mkdir -p "$(dirname "${compatibility_link}")"
  ln -sfn "$(realpath "${INSTALL_ROOT}")" "${compatibility_link}"

  echo
  echo "[bootstrap] done"
  echo "[bootstrap] service root: $(realpath "${INSTALL_ROOT}")"
  echo "[bootstrap] artifact: $(realpath "${artifact_file}")"
  echo "[bootstrap] desired.json: $(realpath "${desired_file}")"
  echo "[bootstrap] runtime.json: $(realpath "${runtime_file}")"
  echo "[bootstrap] docker-compose.yml: $(realpath "${compose_file}")"
  echo "[bootstrap] extracted build context: $(realpath "${extracted_dir}")"
  echo "[bootstrap] current -> $(readlink "${current_link}")"
  echo "[bootstrap] compatibility link: ${compatibility_link} -> $(readlink "${compatibility_link}")"
}

main "$@"
