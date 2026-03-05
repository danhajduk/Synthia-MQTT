#!/usr/bin/env bash
set -euo pipefail

SERVICE_BASE_URL="${SERVICE_BASE_URL:-http://127.0.0.1:18080}"
BOOTSTRAP_ARGS="${BOOTSTRAP_ARGS:---version latest --no-open}"
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
