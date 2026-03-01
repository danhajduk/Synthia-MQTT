#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-}"
if [[ -z "${VERSION}" ]]; then
  echo "Usage: $0 <version-tag> (example: $0 v0.1.1)" >&2
  exit 1
fi

ASSET_NAME="${ASSET_NAME:-addon.tgz}"
SIGNING_KEY="${SIGNING_KEY:-./keys/publisher_private.pem}"
PACKAGE_PATHS="${PACKAGE_PATHS:-manifest.json app frontend}"
REPO_SLUG="${REPO_SLUG:-danhajduk/Synthia-MQTT}"
MKTIME="${MKTIME:-UTC 2026-01-01}"
PUBLISHER_KEY_ID="${PUBLISHER_KEY_ID:-publisher.danhajduk#2026-02}"
OUTPUT_JSON="${OUTPUT_JSON:-release-output.json}"

die() { echo "ERROR: $*" >&2; exit 1; }

command -v tar >/dev/null || die "tar not installed"
command -v sha256sum >/dev/null || die "sha256sum not installed"
command -v openssl >/dev/null || die "openssl not installed"
command -v base64 >/dev/null || die "base64 not installed"
command -v gh >/dev/null || die "gh (GitHub CLI) not installed"

[[ -f "${SIGNING_KEY}" ]] || die "Signing key not found: ${SIGNING_KEY}"

for p in ${PACKAGE_PATHS}; do
  [[ -e "$p" ]] || die "Missing path to package: $p"
done

echo "==> Building deterministic ${ASSET_NAME}"
rm -f "${ASSET_NAME}"

tar --sort=name \
  --owner=0 --group=0 --numeric-owner \
  --mtime="${MKTIME}" \
  -czf "${ASSET_NAME}" ${PACKAGE_PATHS}

echo "==> Calculating SHA256"
SHA256="$(sha256sum "${ASSET_NAME}" | awk '{print $1}')"

echo "==> Generating detached signature"
RELEASE_SIG="$(openssl dgst -sha256 -sign "${SIGNING_KEY}" -binary "${ASSET_NAME}" | base64 -w0)"

echo "==> Ensuring GitHub release exists: ${VERSION}"

if gh release view "${VERSION}" --repo "${REPO_SLUG}" >/dev/null 2>&1; then
  echo "    Release exists."
else
  echo "    Release missing — creating it."
  gh release create "${VERSION}" \
    --repo "${REPO_SLUG}" \
    --title "${VERSION}" \
    --notes ""
fi

echo "==> Uploading ${ASSET_NAME}"
gh release upload "${VERSION}" "${ASSET_NAME}" \
  --repo "${REPO_SLUG}" \
  --clobber

ARTIFACT_URL="https://github.com/${REPO_SLUG}/releases/download/${VERSION}/${ASSET_NAME}"

echo "==> Writing ${OUTPUT_JSON}"

cat > "${OUTPUT_JSON}" <<EOF
{
  "version": "${VERSION}",
  "artifact": {
    "type": "github_release_asset",
    "url": "${ARTIFACT_URL}"
  },
  "sha256": "${SHA256}",
  "publisher_key_id": "${PUBLISHER_KEY_ID}",
  "signature_type": "rsa-sha256",
  "release_sig": "${RELEASE_SIG}"
}
EOF

echo "Done."
echo "Generated ${OUTPUT_JSON}"