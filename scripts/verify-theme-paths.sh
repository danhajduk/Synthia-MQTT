#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-all}"

required_theme_files=(
  "theme/index.css"
  "theme/tokens.css"
  "theme/base.css"
  "theme/components.css"
  "theme/themes/dark.css"
)

check_theme_dir() {
  local root="$1"
  local missing=0

  for rel in "${required_theme_files[@]}"; do
    if [[ ! -f "$root/$rel" ]]; then
      echo "missing: $root/$rel"
      missing=1
    fi
  done

  if [[ $missing -ne 0 ]]; then
    return 1
  fi

  local index_css="$root/theme/index.css"
  rg -q '@import "\./tokens\.css";' "$index_css"
  rg -q '@import "\./base\.css";' "$index_css"
  rg -q '@import "\./components\.css";' "$index_css"
  rg -q '@import "\./themes/dark\.css";' "$index_css"
}

check_dev() {
  check_theme_dir "frontend/src"
  rg -q 'SHARED_THEME_ENTRY_HREF = "/ui/theme/index\.css"' frontend/src/app.js
  echo "dev verification: ok"
}

check_prod() {
  check_theme_dir "frontend/dist"
  rg -q 'SHARED_THEME_ENTRY_HREF = "/ui/theme/index\.css"' frontend/dist/app.js
  echo "prod verification: ok"
}

case "$MODE" in
  dev)
    check_dev
    ;;
  prod)
    check_prod
    ;;
  all)
    check_dev
    check_prod
    ;;
  *)
    echo "usage: $0 [dev|prod|all]" >&2
    exit 2
    ;;
esac
