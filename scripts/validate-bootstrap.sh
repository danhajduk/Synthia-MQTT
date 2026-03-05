#!/usr/bin/env bash
set -euo pipefail

ADDON_PORT="${ADDON_PORT:-18081}"
DEFAULT_HOST_IP="${DEFAULT_HOST_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
if [[ -z "$DEFAULT_HOST_IP" ]]; then
  DEFAULT_HOST_IP="127.0.0.1"
fi
SERVICE_BASE_URL="${SERVICE_BASE_URL:-http://${DEFAULT_HOST_IP}:${ADDON_PORT}}"
BOOTSTRAP_ARGS="${BOOTSTRAP_ARGS:---version latest --no-open --non-interactive --addon-port ${ADDON_PORT}}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOOTSTRAP_SCRIPT="$REPO_ROOT/scripts/bootstrap-install.sh"

echo "[validate-bootstrap] running bootstrap: $BOOTSTRAP_SCRIPT $BOOTSTRAP_ARGS"
# shellcheck disable=SC2086
"$BOOTSTRAP_SCRIPT" $BOOTSTRAP_ARGS

echo "[validate-bootstrap] checking health endpoint"
curl -fsS "${SERVICE_BASE_URL}/healthz" >/dev/null

UI_URL="${SERVICE_BASE_URL}/ui"
echo "[validate-bootstrap] UI URL: ${UI_URL}"
echo "[validate-bootstrap] success"
