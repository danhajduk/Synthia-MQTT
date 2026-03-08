# Synthia MQTT Addon Service

Distributed MQTT addon service running as a standalone external service.

## Repository Layout

- `app/`: FastAPI application code.
- `docker/`: Compose and container build files.
- `frontend/`: Setup/dashboard UI source and build output.
- `runtime/`: Persisted runtime state and generated broker artifacts.
- `scripts/`: Bootstrap, release, and validation scripts.
- `docs/`: Active documentation and mismatch report.

## Quick Start

Bootstrap latest release artifact:

```bash
./scripts/bootstrap-install.sh --version latest
```

Bootstrap specific release tag:

```bash
ADDON_VERSION="$(python3 -c 'import json;print(json.load(open("manifest.json","r",encoding="utf-8"))["version"])')"
./scripts/bootstrap-install.sh --version "v${ADDON_VERSION}"
```

Manual compose startup:

```bash
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 docker compose -f docker/docker-compose.yml up -d
```

Health check:

```bash
curl http://localhost:18080/healthz
```

UI (when `frontend/dist` exists):

```bash
open http://localhost:18080/ui
```

## Implemented API Endpoints

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/version`
- `GET /api/addon/permissions`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`
- `GET /api/install/status`
- `POST /api/install/test-external`
- `POST /api/install/apply`
- `POST /api/install/register-core`
- `POST /api/install/reset`
- `POST /api/broker/restart`
- `POST /api/mqtt/publish`
- `POST /api/ha/discovery/sensor`

## Optional Service-Token Auth

Privileged write endpoints can enforce service-token JWT validation.

Environment variables:

- `SYNTHIA_AUTH_REQUIRED` (`true|false`, default `false`)
- `SYNTHIA_JWT_SIGNING_KEY` (required when auth is enabled)
- `SYNTHIA_TOKEN_AUDIENCE` (optional, defaults to addon id `mqtt`)

## Optional Policy Enforcement

MQTT operation gates can enforce retained policy grants/revocations.

Environment variable:

- `SYNTHIA_POLICY_ENFORCEMENT` (`true|false`, default `false`)

## Telemetry Reporting

Usage reporting to Core is buffered and best-effort (`POST /api/telemetry/usage`).

Environment variables:

- `SYNTHIA_TELEMETRY_ENABLED` (`true|false`, default `true`)
- `SYNTHIA_TELEMETRY_MAX_QUEUE` (default `500`)
- `SYNTHIA_TELEMETRY_FLUSH_INTERVAL_S` (default `15`)
- `SYNTHIA_TELEMETRY_TIMEOUT_S` (default `3`)

## Documentation Index

- `docs/core.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/mismatch-report.md`
- `docs/archive/README.md`

## Manifest Summary

`manifest.json` currently declares:

- `schema_version`: `1.1`
- `id`: `mqtt`
- `version`: sourced from `manifest.json` (`python3 -c 'import json;print(json.load(open("manifest.json","r",encoding="utf-8"))["version"])'`)
- `package_profile`: `standalone_service`
- permissions: `network.egress`, `mqtt.publish`, `mqtt.subscribe`
