# Deployment Documentation

## Compose Stack

File: `docker/docker-compose.yml`

Services:

- `mosquitto`: MQTT broker with persistent data and logs.
- `mqtt-addon`: FastAPI service that connects to broker and serves addon APIs.

Ports:

- `1883`: MQTT broker
- `18080`: Addon HTTP API

## Startup

```bash
docker compose -f docker/docker-compose.yml up -d
```

## Shutdown

```bash
docker compose -f docker/docker-compose.yml down
```
