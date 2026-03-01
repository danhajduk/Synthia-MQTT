#!/usr/bin/env bash
set -euo pipefail

# Creates a signed addon artifact using manifest.json.
# Outputs in ./dist:
#   addon.tgz, addon.tgz.sig, addon.sha256, addon.release_sig.b64, catalog-snippet.json

MANIFEST="manifest.json"
OUTDIR="dist"
KEY=""
PUBLISHER_KEY_ID=""
ARTIFACT_URL=""
INCLUDE_EXTRA=()

die(){ echo "ERROR: $*" >&2; exit 1; }
have(){ command -v "$1" >/dev/null 2>&1; }

# JSON getters: prefer jq; fallback to python3 with -c (no heredocs).
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
# support ".a.b.c" only
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) MANIFEST="$2"; shift 2;;
    --out) OUTDIR="$2"; shift 2;;
    --key) KEY="$2"; shift 2;;
    --publisher-key-id) PUBLISHER_KEY_ID="$2"; shift 2;;
    --artifact-url) ARTIFACT_URL="$2"; shift 2;;
    --include) INCLUDE_EXTRA+=("$2"); shift 2;;
    -h|--help)
      echo "Usage: $0 --key <publisher_private.pem> --publisher-key-id <id> --artifact-url <url> [--manifest manifest.json] [--out dist]"
      exit 0
      ;;
    *) die "Unknown arg: $1";;
  esac
done

[[ -f "$MANIFEST" ]] || die "Manifest not found: $MANIFEST"
[[ -n "$KEY" ]] || die "--key is required"
[[ -f "$KEY" ]] || die "Private key not found: $KEY"
[[ -n "$PUBLISHER_KEY_ID" ]] || die "--publisher-key-id is required"
[[ -n "$ARTIFACT_URL" ]] || die "--artifact-url is required"

have openssl || die "openssl not found"
have tar || die "tar not found"
have sha256sum || die "sha256sum not found"
have base64 || die "base64 not found"

ADDON_ID="$(json_get '.id')"
ADDON_NAME="$(json_get '.name')"
ADDON_VERSION="$(json_get '.version')"

CORE_MIN="$(json_get '.core_min_version')"
CORE_MAX="$(json_get '.core_max_version')"
if [[ -z "$CORE_MIN" ]]; then CORE_MIN="$(json_get '.compatibility.core_min_version')"; fi
if [[ -z "$CORE_MAX" ]]; then CORE_MAX="$(json_get '.compatibility.core_max_version')"; fi

[[ -n "$ADDON_ID" ]] || die "manifest.json missing required field: id"
[[ -n "$ADDON_VERSION" ]] || die "manifest.json missing required field: version"
[[ -n "$ADDON_NAME" ]] || ADDON_NAME="$ADDON_ID"
[[ -n "$CORE_MIN" ]] || CORE_MIN="0.0.0"

mkdir -p "$OUTDIR"

# Determine packaging paths.
PATHS=()
BACKEND_PATH="$(json_get '.backend')"
FRONTEND_PATH="$(json_get '.frontend')"
WORKER_PATH="$(json_get '.worker')"

if [[ -n "$BACKEND_PATH" || -n "$FRONTEND_PATH" || -n "$WORKER_PATH" ]]; then
  [[ -n "$BACKEND_PATH" ]] && PATHS+=("${BACKEND_PATH#./}")
  [[ -n "$FRONTEND_PATH" ]] && PATHS+=("${FRONTEND_PATH#./}")
  [[ -n "$WORKER_PATH" ]] && PATHS+=("${WORKER_PATH#./}")
else
  [[ -d backend ]] && PATHS+=(backend)
  [[ -d frontend ]] && PATHS+=(frontend)
  [[ -d worker ]] && PATHS+=(worker)
fi

# Optional manifest array: paths:[...]
while IFS= read -r p; do
  [[ -n "$p" ]] && PATHS+=("${p#./}")
done < <(json_list_get '.paths' || true)

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

ARTIFACT="$OUTDIR/addon.tgz"
SIGFILE="$OUTDIR/addon.tgz.sig"
SHAFILE="$OUTDIR/addon.sha256"
B64FILE="$OUTDIR/addon.release_sig.b64"
SNIPFILE="$OUTDIR/catalog-snippet.json"

echo "== Packaging =="
echo "Addon: $ADDON_ID ($ADDON_NAME) v$ADDON_VERSION"
echo "Include:"
printf " - %s\n" "${FILES[@]}"

tar -czf "$ARTIFACT" "${FILES[@]}"

SHA256="$(sha256sum "$ARTIFACT" | awk '{print $1}')"
echo "$SHA256  addon.tgz" | tee "$SHAFILE"

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
