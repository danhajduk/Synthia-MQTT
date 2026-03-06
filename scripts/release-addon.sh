#!/usr/bin/env bash
set -euo pipefail

########################################
# CONFIG
########################################

VERSION="${1:-}"
[[ -z "${VERSION}" ]] && { echo "Usage: $0 <version> (example: 0.1.3)"; exit 1; }

ASSET_NAME="${ASSET_NAME:-addon.tgz}"
SIGNING_KEY="${SIGNING_KEY:-./keys/publisher_private.pem}"
REPO_SLUG="${REPO_SLUG:-danhajduk/Synthia-MQTT}"
PUBLISHER_KEY_ID="${PUBLISHER_KEY_ID:-publisher.danhajduk#2026-02}"
PACKAGE_PROFILE="${PACKAGE_PROFILE:-standalone_service}"
CHANNEL="${CHANNEL:-stable}"
OUTPUT_JSON="${OUTPUT_JSON:-release-output.json}"

# What gets packaged (compose-bundle profile)
PACKAGE_PATHS="${PACKAGE_PATHS:-manifest.json docker app frontend requirements.txt}"

########################################
# VALIDATION
########################################

command -v tar >/dev/null || { echo "tar missing"; exit 1; }
command -v sha256sum >/dev/null || { echo "sha256sum missing"; exit 1; }
command -v openssl >/dev/null || { echo "openssl missing"; exit 1; }
command -v base64 >/dev/null || { echo "base64 missing"; exit 1; }
command -v gh >/dev/null || { echo "gh CLI missing"; exit 1; }

[[ -f "${SIGNING_KEY}" ]] || { echo "Signing key not found: ${SIGNING_KEY}"; exit 1; }

for p in ${PACKAGE_PATHS}; do
  [[ -e "$p" ]] || { echo "Missing path to package: $p"; exit 1; }
done

if echo " ${PACKAGE_PATHS} " | grep -q " frontend "; then
  if [[ ! -d "frontend/dist" ]]; then
    if command -v npm >/dev/null 2>&1 && [[ -f "frontend/package.json" ]]; then
      echo "==> Building frontend assets"
      (cd frontend && npm run build)
    else
      echo "frontend/dist missing and npm unavailable; cannot package UI assets"
      exit 1
    fi
  fi
fi

########################################
# BUILD DETERMINISTIC TARBALL
########################################

echo "==> Building deterministic ${ASSET_NAME}"
rm -f "${ASSET_NAME}"

STAGE_DIR="$(mktemp -d)"
cleanup_stage() {
  rm -rf "${STAGE_DIR}"
}
trap cleanup_stage EXIT

for p in ${PACKAGE_PATHS}; do
  cp -a "$p" "${STAGE_DIR}/"
done

if [[ -f "${STAGE_DIR}/docker/Dockerfile" && ! -f "${STAGE_DIR}/Dockerfile" ]]; then
  cp "${STAGE_DIR}/docker/Dockerfile" "${STAGE_DIR}/Dockerfile"
fi

tar --sort=name \
  --owner=0 --group=0 --numeric-owner \
  --mtime="UTC 2026-01-01" \
  -C "${STAGE_DIR}" \
  -czf "${ASSET_NAME}" .

########################################
# SHA256
########################################

echo "==> Calculating SHA256"
SHA256="$(sha256sum "${ASSET_NAME}" | awk '{print $1}')"

########################################
# OPTION A SIGNING (ed25519 over SHA256 digest bytes)
########################################

echo "==> Generating ed25519 signature (Option A)"

TMP_DIGEST="$(mktemp)"
TMP_SIG="$(mktemp)"

# Convert SHA256 hex -> raw digest bytes (portable, no xxd/openssl-hex)
python3 - <<PY > "${TMP_DIGEST}"
import binascii
import sys
sys.stdout.buffer.write(binascii.unhexlify("${SHA256}"))
PY

# Sign digest bytes with ed25519 private key
openssl pkeyutl -sign \
  -inkey "${SIGNING_KEY}" \
  -rawin \
  -in "${TMP_DIGEST}" \
  -out "${TMP_SIG}"

RELEASE_SIG="$(base64 -w0 "${TMP_SIG}")"

rm -f "${TMP_DIGEST}" "${TMP_SIG}"

########################################
# GITHUB RELEASE
########################################

echo "==> Ensuring GitHub release exists: v${VERSION}"

if gh release view "v${VERSION}" --repo "${REPO_SLUG}" >/dev/null 2>&1; then
  echo "    Release exists."
else
  gh release create "v${VERSION}" \
    --repo "${REPO_SLUG}" \
    --title "v${VERSION}" \
    --notes ""
fi

echo "==> Uploading ${ASSET_NAME}"
gh release upload "v${VERSION}" "${ASSET_NAME}" \
  --repo "${REPO_SLUG}" \
  --clobber

ARTIFACT_URL="https://github.com/${REPO_SLUG}/releases/download/v${VERSION}/${ASSET_NAME}"

########################################
# OUTPUT CATALOG SNIPPET
########################################

echo "==> Writing ${OUTPUT_JSON}"

cat > "${OUTPUT_JSON}" <<EOF
{
  "version": "${VERSION}",
  "channel": "${CHANNEL}",
  "package_profile": "${PACKAGE_PROFILE}",
  "artifact": {
    "type": "github_release_asset",
    "url": "${ARTIFACT_URL}"
  },
  "sha256": "${SHA256}",
  "publisher_key_id": "${PUBLISHER_KEY_ID}",
  "signature": {
    "type": "ed25519",
    "value": "${RELEASE_SIG}"
  },
  "runtime": {
    "orchestrator": "docker_compose",
    "strategy": "compose_bundle",
    "compose_path": "docker/docker-compose.yml"
  }
}
EOF

echo "==========================================="
echo "Release complete."
echo "Version: ${VERSION}"
echo "SHA256: ${SHA256}"
echo "Artifact: ${ARTIFACT_URL}"
echo "Catalog snippet written to: ${OUTPUT_JSON}"
echo "==========================================="
