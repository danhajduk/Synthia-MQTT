# Synthia Addon MQTT

Phase 1 scaffold for a distributed Synthia MQTT addon service.

## Structure

- `app/`: FastAPI entrypoint plus API/service/model modules.
- `docker/`: compose and broker config scaffold.
- `runtime/`: persistent runtime data volume.

## Run (scaffold check)

From repository root:

```bash
docker compose -f Synthia-Addon-MQTT/docker/docker-compose.yml up
```

Then open `http://localhost:18080/healthz`.

## Addon Contract Endpoints (Phase 2)

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`

Configuration defaults come from environment variables and overrides are persisted at `runtime/config.json`.
