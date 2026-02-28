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

## MQTT Runtime (Phase 3)

- Uses `paho-mqtt` for broker connectivity.
- Sets retained LWT on `synthia/addons/mqtt/health` with `offline` payload.
- Publishes retained announce payload to `synthia/addons/mqtt/announce` on connect.
- Publishes retained health every 15 seconds.
- Automatically reconnects when broker connectivity is lost.

## MQTT Publish API (Phase 4)

- `POST /api/mqtt/publish`
- Validates non-empty topic.
- Accepts any payload type and JSON-encodes `dict`/`list` payloads automatically.

## Home Assistant Discovery API (Phase 5)

- `POST /api/ha/discovery/sensor`
- Publishes retained sensor discovery config to `homeassistant/sensor/{unique_id}/config`.
