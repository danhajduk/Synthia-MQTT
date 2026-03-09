#!/usr/bin/env bash
set -euo pipefail

check_app() {
  local file="$1"
  rg -q 'classList\.add\("card"\)' "$file"
  rg -q 'classList\.add\("btn"\)' "$file"
  rg -q 'classList\.add\("sx-input"\)' "$file"
  rg -q 'classList\.add\("sx-status"\)' "$file"
  rg -q 'classList\.add\("sx-list"\)' "$file"
  rg -q 'classList\.add\("sx-list-item"\)' "$file"
  rg -q 'classList\.toggle\("core-theme-fallback"' "$file"
  rg -q 'classList\.toggle\("core-theme-detected"' "$file"
}

check_styles() {
  local file="$1"
  rg -q ':root\.core-theme-fallback \.banner' "$file"
  rg -q ':root\.core-theme-fallback \.steps li\.active' "$file"
  rg -q ':root\.core-theme-fallback \.optional-group-card\[data-status="active"\]' "$file"
  rg -q 'html\.in-iframe \.layout' "$file"
}

check_components() {
  local file="$1"
  rg -q ':root\.core-theme-fallback \.card' "$file"
  rg -q ':root\.core-theme-fallback \.btn-secondary' "$file"
  rg -q ':root\.core-theme-fallback \.sx-input' "$file"
  rg -q ':root\.core-theme-fallback \.sx-status' "$file"
  rg -q ':root\.core-theme-fallback \.sx-list-item' "$file"
  rg -q ':root\.core-theme-fallback \.sx-table' "$file"
}

check_app frontend/src/app.js
check_styles frontend/src/styles.css
check_components frontend/src/theme/components.css

if [[ -f frontend/dist/app.js ]]; then
  check_app frontend/dist/app.js
fi
if [[ -f frontend/dist/styles.css ]]; then
  check_styles frontend/dist/styles.css
fi
if [[ -f frontend/dist/theme/components.css ]]; then
  check_components frontend/dist/theme/components.css
fi

echo "iframe style-language verification: ok"
