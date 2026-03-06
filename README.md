# Synthia MQTT Addon Service

Distributed MQTT addon service running from the repository root at `~/Projects/Synthia-MQTT`.
This artifact runs as a standalone external service and does not manage an embedded broker.

## Repository Layout

- `app/`: FastAPI application code.
- `docker/`: Compose stack and Mosquitto broker config.
- `frontend/`: Embedded setup wizard source (`src/`) and static build output (`dist/`).
- `runtime/`: Persistent runtime data.
- `scripts/`: Operational scripts.
- `Ducuments/`: Module-level documentation.

## Local Workflow Files

- Local workflow/tracking files like `New_tasks.txt` and `completed_task.txt` are intentionally ignored by Git.

## Quick Start

Bootstrap v2 (latest release, addon-only startup, readiness-aware UI handoff):

```bash
./scripts/bootstrap-install.sh --version latest
```

Optional bootstrap controls:

```bash
./scripts/bootstrap-install.sh --version latest --no-open --timeout-seconds 90 --addon-port 19080 --bind 127.0.0.1
```

Bootstrap demo validation script:

```bash
./scripts/validate-bootstrap.sh
```

Manual compose startup (alternative to bootstrap):

```bash
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 docker compose -f docker/docker-compose.yml up -d
```

`docker/docker-compose.yml` builds the service image using `docker/Dockerfile`.

Set `ANNOUNCE_BASE_URL` to the externally reachable API URL so MQTT announce payloads expose the correct address.

Health check:

```bash
curl http://localhost:18080/healthz
```

UI (when `frontend/dist` exists):

```bash
open http://localhost:18080/ui
```

Build/update frontend static assets:

```bash
cd frontend && npm run build
```

Bootstrap latest addon release with interactive install prompts:

```bash
./scripts/bootstrap-install.sh
```

Current published release target: `v0.1.9`.

Bootstrap install layout (current):
- install root: `./SynthiaAddons/Synthia-MQTT`
- root files: `desired.json`, `runtime.json`, `current -> versions/<version>`
- version files: `versions/<version>/addon.tgz`, `versions/<version>/extracted`, `versions/<version>/docker-compose.yml`
- `extracted` is a source-linked runtime workspace prepared from `MAIN_ADDON_ROOT` (defaults to repo root); `addon.tgz` is retained and not untarred.
- bootstrap also extracts `docker/docker-compose.yml` from the artifact into `versions/<version>/docker-compose.yml`.
- service link: `./SynthiaAddons/service/<addon_id> -> ./SynthiaAddons/Synthia-MQTT`

The bootstrap script asks for:
- whether to install a local MQTT broker container
- Core host URL (optional, for endpoint registration)
- addon public base URL, MQTT connection settings, and whether to start services now

## API Endpoints

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
- `POST /api/broker/restart`
- `POST /api/mqtt/publish`
- `POST /api/ha/discovery/sensor`

## Standalone Service Lifecycle

- Addon self-registers and publishes retained announce/health via MQTT.
- Core acts as control plane (desired state, registry, UI), not data-plane runtime owner.
- Supervisor/orchestrator handles standalone lifecycle reconciliation and activation.

## Rebuild And Restart

```bash
./scripts/rebuild.sh
```

Validate health, announce, and optional Core proxy flow:

```bash
SERVICE_BASE_URL=http://localhost:18080 MQTT_HOST=10.0.0.100 ./scripts/validate-service-flow.sh
```

## Documentation Index

- `Ducuments/overview.md`
- `Ducuments/api.md`
- `Ducuments/services.md`
- `Ducuments/models.md`
- `Ducuments/deployment.md`
- `Ducuments/scripts.md`
- `Ducuments/operations.md`

## Manifest Standard Alignment

`manifest.json` follows Synthia Addon Standard v1.1:

- `schema_version = 1.1`
- `package_profile = standalone_service`
- canonical permissions: `network.egress`, `mqtt.publish`, `mqtt.subscribe`
- `entrypoints.service = app/main.py` and `entrypoints.ui = frontend`

## Artifact Extraction Layout

`addon.tgz` now extracts with this canonical structure:

```text
<artifact-root>/
  manifest.json
  requirements.txt
  Dockerfile
  app/
  frontend/        (optional)
    dist/
  docker/          (optional)
    Dockerfile     (optional)
    docker-compose.yml (optional)
```
