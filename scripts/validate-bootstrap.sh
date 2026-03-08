#!/usr/bin/env bash
set -euo pipefail

ADDON_PORT="${ADDON_PORT:-18081}"
DEFAULT_HOST_IP="${DEFAULT_HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
if [[ -z "$DEFAULT_HOST_IP" ]]; then
  DEFAULT_HOST_IP="127.0.0.1"
fi
SERVICE_BASE_URL="${SERVICE_BASE_URL:-http://${DEFAULT_HOST_IP}:${ADDON_PORT}}"
BOOTSTRAP_ARGS="${BOOTSTRAP_ARGS:---version latest}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOOTSTRAP_SCRIPT="$REPO_ROOT/scripts/bootstrap-install.sh"

echo "[validate-bootstrap] running bootstrap: $BOOTSTRAP_SCRIPT $BOOTSTRAP_ARGS"
# shellcheck disable=SC2086
"$BOOTSTRAP_SCRIPT" $BOOTSTRAP_ARGS

echo "[validate-bootstrap] checking SSAP layout invariants"
python3 - "$REPO_ROOT" <<'PY'
import json
import os
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
addons_root = repo_root / "SynthiaAddons"
service_root = addons_root / "services" / "mqtt"
legacy_root = addons_root / "Synthia-MQTT"

required_files = [
    service_root / "desired.json",
    service_root / "runtime.json",
]
for path in required_files:
    if not path.exists():
        raise SystemExit(f"missing required file: {path}")

current_link = service_root / "current"
if not current_link.is_symlink():
    raise SystemExit(f"current is not a symlink: {current_link}")

current_target = (service_root / os.readlink(current_link)).resolve()
required_version_files = [
    current_target / "addon.tgz",
    current_target / "docker-compose.yml",
    current_target / "extracted",
    current_target / "extracted" / "Dockerfile",
]
for path in required_version_files:
    if not path.exists():
        raise SystemExit(f"missing version artifact file: {path}")

if not legacy_root.is_symlink():
    raise SystemExit(f"legacy compatibility link missing: {legacy_root}")
legacy_target = legacy_root.resolve()
if legacy_target != service_root.resolve():
    raise SystemExit(f"legacy link target mismatch: {legacy_target} != {service_root.resolve()}")

desired = json.loads((service_root / "desired.json").read_text(encoding="utf-8"))
runtime = json.loads((service_root / "runtime.json").read_text(encoding="utf-8"))
if desired.get("addon_id") != "mqtt":
    raise SystemExit("desired.json addon_id mismatch")
if desired.get("ssap_version") != "1.0":
    raise SystemExit("desired.json ssap_version mismatch")
if runtime.get("addon_id") != "mqtt":
    raise SystemExit("runtime.json addon_id mismatch")
if runtime.get("ssap_version") != "1.0":
    raise SystemExit("runtime.json ssap_version mismatch")

current_version = current_target.name
if desired.get("pinned_version") != current_version:
    raise SystemExit(
        f"desired.json pinned_version mismatch: {desired.get('pinned_version')} != {current_version}"
    )
if runtime.get("active_version") != current_version:
    raise SystemExit(
        f"runtime.json active_version mismatch: {runtime.get('active_version')} != {current_version}"
    )

print("ssap layout checks passed")
PY

echo "[validate-bootstrap] checking health endpoint"
curl -fsS "${SERVICE_BASE_URL}/healthz" >/dev/null

UI_URL="${SERVICE_BASE_URL}/ui"
echo "[validate-bootstrap] UI URL: ${UI_URL}"
echo "[validate-bootstrap] success"
