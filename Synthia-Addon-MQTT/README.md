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
