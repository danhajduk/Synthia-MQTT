#!/usr/bin/env bash
set -euo pipefail

check_file() {
  local file="$1"

  rg -q 'document\.documentElement\.classList\.toggle\("in-iframe"' "$file"
  rg -q 'mirrorParentThemeIfAvailable\(\)' "$file"
  rg -q 'applyThemeMode\(hasCoreThemeTokens\(\)\)' "$file"
}

check_css() {
  local file="$1"

  rg -q 'html\.in-iframe \.layout' "$file"
  rg -q 'html\.in-iframe \.hero' "$file"
}

check_file frontend/src/app.js
check_css frontend/src/styles.css

if [[ -f frontend/dist/app.js ]]; then
  check_file frontend/dist/app.js
fi

if [[ -f frontend/dist/styles.css ]]; then
  check_css frontend/dist/styles.css
fi

echo "iframe theme verification: ok"
