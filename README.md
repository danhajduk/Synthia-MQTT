# Synthia MQTT Addon Service

Distributed MQTT addon service running from the repository root at `~/Projects/Synthia-MQTT`.

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

```bash
docker compose -f docker/docker-compose.yml up -d
```

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

## API Endpoints

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`
- `GET /api/install/status`
- `POST /api/install/test-external`
- `POST /api/install/apply`
- `POST /api/broker/restart`
- `POST /api/mqtt/publish`
- `POST /api/ha/discovery/sensor`

## Rebuild And Restart

```bash
./scripts/rebuild.sh
```

## Documentation Index

- `Ducuments/overview.md`
- `Ducuments/api.md`
- `Ducuments/services.md`
- `Ducuments/models.md`
- `Ducuments/deployment.md`
- `Ducuments/scripts.md`

## Release Artifact Layout

`manifest.json` now packages the service runtime layout directly:

- `app/`
- `frontend/`
- `requirements.txt`
