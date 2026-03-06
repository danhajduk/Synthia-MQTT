#!/usr/bin/env bash
set -euo pipefail

# Creates a signed addon artifact using manifest.json.
# Outputs in ./dist:
#   addon.tgz, addon.tgz.sig, addon.sha256, addon.release_sig.b64, catalog-snippet.json
#
# Defaults:
# - manifest.json in repo root
# - keys/ directory contains signing materials
#   - publisher_private.pem
#   - publisher_key_id.txt
#   - artifact_base_url.txt (optional)
#
# Optional environment variables:
# - ARTIFACT_URL_TEMPLATE (supports {version})
# - ASSET_NAME (default addon.tgz)

MANIFEST="manifest.json"
OUTDIR="dist"
KEY=""
PUBLISHER_KEY_ID=""
ARTIFACT_URL=""
ARTIFACT_URL_TEMPLATE="${ARTIFACT_URL_TEMPLATE:-}"
ASSET_NAME="${ASSET_NAME:-addon.tgz}"
KEYS_DIR="keys"
INCLUDE_EXTRA=()

die(){ echo "ERROR: $*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

json_get() {
  local expr="$1"
  if have jq; then
    jq -r "$expr // empty" "$MANIFEST"
    return
  fi
  have python3 || die "Need jq or python3 to parse manifest"
  python3 -c 'import json,sys
m=json.load(open(sys.argv[1],"r",encoding="utf-8"))
path=sys.argv[2].strip()
parts=[p for p in path.lstrip(".").split(".") if p]
cur=m
for p in parts:
  if isinstance(cur,dict) and p in cur: cur=cur[p]
  else: cur=""; break
if cur is None: cur=""
if isinstance(cur,(dict,list)): import json as j; print(j.dumps(cur))
else: print(str(cur))
' "$MANIFEST" "$expr"
}

json_list_get() {
  local expr="$1"
  if have jq; then
    jq -r "$expr[]? // empty" "$MANIFEST"
    return
  fi
  have python3 || exit 0
  python3 -c 'import json,sys
m=json.load(open(sys.argv[1],"r",encoding="utf-8"))
path=sys.argv[2].strip()
parts=[p for p in path.lstrip(".").split(".") if p]
cur=m
for p in parts:
  if isinstance(cur,dict) and p in cur: cur=cur[p]
  else: cur=[]; break
if not isinstance(cur,list): cur=[]
for item in cur:
  if isinstance(item,(dict,list)): import json as j; print(j.dumps(item))
  else: print(str(item))
' "$MANIFEST" "$expr"
}

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --manifest <path>       (default: manifest.json)
  --out <dir>             (default: dist)
  --keys-dir <dir>        (default: keys)
  --key <pem>             (override private key)
  --publisher-key-id <id> (override key id)
  --artifact-url <url>    (override artifact url)
  --include <path>        (extra include)
  -h|--help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2;;
    --out) OUTDIR="$2"; shift 2;;
    --keys-dir) KEYS_DIR="$2"; shift 2;;
    --key) KEY="$2"; shift 2;;
    --publisher-key-id) PUBLISHER_KEY_ID="$2"; shift 2;;
    --artifact-url) ARTIFACT_URL="$2"; shift 2;;
    --include) INCLUDE_EXTRA+=("$2"); shift 2;;
    -h|--help) usage; exit 0;;
    *) die "Unknown arg: $1";;
  esac
done

[[ -f "$MANIFEST" ]] || die "Manifest not found: $MANIFEST"

have openssl || die "openssl not found"
have tar || die "tar not found"
have sha256sum || die "sha256sum not found"
have base64 || die "base64 not found"

# --- Load manifest basics ---
SCHEMA_VERSION="$(json_get '.schema_version')"
ADDON_ID="$(json_get '.id')"
ADDON_NAME="$(json_get '.name')"
ADDON_VERSION="$(json_get '.version')"
PACKAGE_PROFILE="$(json_get '.package_profile')"
CORE_MIN="$(json_get '.compatibility.core_min_version')"
CORE_MAX="$(json_get '.compatibility.core_max_version')"

[[ -n "$SCHEMA_VERSION" ]] || die "manifest.json missing required field: schema_version"
[[ -n "$ADDON_ID" ]] || die "manifest.json missing required field: id"
[[ -n "$ADDON_VERSION" ]] || die "manifest.json missing required field: version"
[[ -n "$ADDON_NAME" ]] || ADDON_NAME="$ADDON_ID"
[[ -n "$PACKAGE_PROFILE" ]] || die "manifest.json missing required field: package_profile"
[[ -n "$CORE_MIN" ]] || die "manifest.json missing required field: compatibility.core_min_version"
if [[ "$SCHEMA_VERSION" != "1.1" ]]; then
  die "manifest schema_version must be 1.1 for SAS v1.1 signing (found: $SCHEMA_VERSION)"
fi

# --- Auto-find key + key id from keys dir ---
if [[ -z "$KEY" ]]; then
  if [[ -f "$KEYS_DIR/publisher_private.pem" ]]; then
    KEY="$KEYS_DIR/publisher_private.pem"
  else
    # first .pem in keys dir
    KEY="$(ls -1 "$KEYS_DIR"/*.pem 2>/dev/null | head -n 1 || true)"
  fi
fi

if [[ -z "$PUBLISHER_KEY_ID" ]]; then
  if [[ -f "$KEYS_DIR/publisher_key_id.txt" ]]; then
    PUBLISHER_KEY_ID="$(tr -d '\r\n' < "$KEYS_DIR/publisher_key_id.txt")"
  else
    # fallback: first file matching *.key_id or *.kid
    local_id_file="$(ls -1 "$KEYS_DIR"/*.key_id "$KEYS_DIR"/*.kid 2>/dev/null | head -n 1 || true)"
    if [[ -n "${local_id_file:-}" ]]; then
      PUBLISHER_KEY_ID="$(tr -d '\r\n' < "$local_id_file")"
    fi
  fi
fi

[[ -n "$KEY" ]] || die "No private key found. Provide --key or add keys/publisher_private.pem"
[[ -f "$KEY" ]] || die "Private key not found: $KEY"
[[ -n "$PUBLISHER_KEY_ID" ]] || die "No publisher key id found. Provide --publisher-key-id or add keys/publisher_key_id.txt"

# --- Determine artifact URL ---
URL_TEMPLATE="$ARTIFACT_URL_TEMPLATE"
if [[ -z "$URL_TEMPLATE" && -f "$KEYS_DIR/artifact_url_template.txt" ]]; then
  URL_TEMPLATE="$(tr -d '\r\n' < "$KEYS_DIR/artifact_url_template.txt")"
fi

if [[ -z "$ARTIFACT_URL" ]]; then
  if [[ -n "$URL_TEMPLATE" ]]; then
    ARTIFACT_URL="${URL_TEMPLATE//\{version\}/$ADDON_VERSION}"
  elif [[ -f "$KEYS_DIR/artifact_base_url.txt" ]]; then
    base="$(tr -d '\r\n' < "$KEYS_DIR/artifact_base_url.txt")"
    # expect base like: https://github.com/owner/repo/releases/download
    ARTIFACT_URL="${base%/}/v${ADDON_VERSION}/${ASSET_NAME}"
  else
    # derive from git remote (GitHub https or ssh)
    REPO_URL="$(git config --get remote.origin.url 2>/dev/null || true)"
    if [[ -z "$REPO_URL" ]]; then
      die "artifact url not provided and git remote not found. Provide --artifact-url, ARTIFACT_URL_TEMPLATE, or keys/artifact_base_url.txt"
    fi
    # Normalize to owner/repo
    # https://github.com/owner/repo.git  OR git@github.com:owner/repo.git
    if [[ "$REPO_URL" =~ github\.com[:/]+([^/]+)/([^/.]+) ]]; then
      owner="${BASH_REMATCH[1]}"
      repo="${BASH_REMATCH[2]}"
      ARTIFACT_URL="https://github.com/${owner}/${repo}/releases/download/v${ADDON_VERSION}/${ASSET_NAME}"
    else
      die "Cannot derive GitHub artifact URL from remote: $REPO_URL. Provide --artifact-url or ARTIFACT_URL_TEMPLATE"
    fi
  fi
fi

[[ -n "$ARTIFACT_URL" ]] || die "artifact url could not be determined"

mkdir -p "$OUTDIR"

# --- Determine packaging paths from manifest.paths ---
PATHS=()
while IFS= read -r p; do
  [[ -n "$p" ]] && PATHS+=("${p#./}")
done < <(json_list_get '.paths' || true)
if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=(app frontend requirements.txt)
fi

FILES=( "$MANIFEST" )
for p in "${PATHS[@]}"; do
  [[ -e "$p" ]] && FILES+=( "$p" )
done
for p in "${INCLUDE_EXTRA[@]:-}"; do
  [[ -e "$p" ]] && FILES+=( "$p" )
done

# De-dupe
DEDUP=()
declare -A SEEN
for f in "${FILES[@]}"; do
  if [[ -z "${SEEN[$f]+x}" ]]; then
    SEEN[$f]=1
    DEDUP+=("$f")
  fi
done
FILES=("${DEDUP[@]}")

ARTIFACT="$OUTDIR/$ASSET_NAME"
SIGFILE="$OUTDIR/$ASSET_NAME.sig"
SHAFILE="$OUTDIR/${ASSET_NAME}.sha256"
B64FILE="$OUTDIR/addon.release_sig.b64"
SNIPFILE="$OUTDIR/catalog-snippet.json"

echo "== Packaging =="
echo "Addon: $ADDON_ID ($ADDON_NAME) v$ADDON_VERSION"
echo "Key: $KEY"
echo "Key ID: $PUBLISHER_KEY_ID"
echo "Artifact URL: $ARTIFACT_URL"
echo "Include:"
printf " - %s\n" "${FILES[@]}"

STAGE_DIR="$(mktemp -d)"
cleanup_stage() {
  rm -rf "$STAGE_DIR"
}
trap cleanup_stage EXIT

for f in "${FILES[@]}"; do
  cp -a "$f" "$STAGE_DIR/"
done

if [[ -f "$STAGE_DIR/docker/Dockerfile" && ! -f "$STAGE_DIR/Dockerfile" ]]; then
  cp "$STAGE_DIR/docker/Dockerfile" "$STAGE_DIR/Dockerfile"
fi

tar -czf "$ARTIFACT" -C "$STAGE_DIR" .

SHA256="$(sha256sum "$ARTIFACT" | awk '{print $1}')"
echo "$SHA256  $ASSET_NAME" | tee "$SHAFILE"

echo "== Signing artifact (detached sig) =="
openssl dgst -sha256 -sign "$KEY" -out "$SIGFILE" "$ARTIFACT"

echo "== Base64 signature (single line) =="
if base64 --help 2>/dev/null | grep -q -- '-w'; then
  B64SIG="$(base64 -w 0 "$SIGFILE")"
else
  B64SIG="$(base64 -b 0 "$SIGFILE")"
fi
echo "$B64SIG" | tee "$B64FILE" >/dev/null

REPO_URL="$(git config --get remote.origin.url 2>/dev/null || true)"

CORE_MAX_JSON="null"
if [[ -n "${CORE_MAX:-}" && "$CORE_MAX" != "null" ]]; then
  CORE_MAX_JSON="\"$CORE_MAX\""
fi

cat > "$SNIPFILE" <<SNIP
{
  "addon_id": "$ADDON_ID",
  "name": "$ADDON_NAME",
  "repo": "$REPO_URL",
  "releases": [
    {
      "version": "$ADDON_VERSION",
      "package_profile": "$PACKAGE_PROFILE",
      "core_min": "$CORE_MIN",
      "core_max": $CORE_MAX_JSON,
      "artifact": {
        "type": "github_release_asset",
        "url": "$ARTIFACT_URL"
      },
      "sha256": "$SHA256",
      "publisher_key_id": "$PUBLISHER_KEY_ID",
      "release_sig": "$B64SIG"
    }
  ]
}
SNIP

echo "== Catalog snippet =="
cat "$SNIPFILE"

echo
echo "DONE."
echo "Artifact:    $ARTIFACT"
echo "Signature:   $SIGFILE"
echo "SHA256 file: $SHAFILE"
echo "Sig b64:     $B64FILE"
echo "Snippet:     $SNIPFILE"
