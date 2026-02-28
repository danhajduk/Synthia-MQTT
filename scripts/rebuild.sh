#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker/docker-compose.yml"

cd "$ROOT_DIR"

echo "[rebuild] stopping stack"
docker compose -f "$COMPOSE_FILE" down --remove-orphans

echo "[rebuild] rebuilding images"
docker compose -f "$COMPOSE_FILE" build --no-cache

echo "[rebuild] starting stack"
docker compose -f "$COMPOSE_FILE" up -d --force-recreate

echo "[rebuild] stack status"
docker compose -f "$COMPOSE_FILE" ps
