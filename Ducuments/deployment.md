# Deployment Documentation

## Compose Stack

File: `docker/docker-compose.yml`

Services:

- `mosquitto`: MQTT broker with persistent data and logs.
- `mqtt-addon` (`Synthia-MQTT`): FastAPI service that connects to broker and serves addon APIs.

Ports:

- `1883`: MQTT broker
- `18080`: Addon HTTP API

## Startup

```bash
docker compose -f docker/docker-compose.yml up -d
```

Start with embedded Mosquitto:

```bash
docker compose -f docker/docker-compose.yml --profile embedded up -d
```

## Embedded Broker Restart API

`POST /api/broker/restart` can restart the embedded `mosquitto` container automatically only when
`/var/run/docker.sock:/var/run/docker.sock` is mounted into the `mqtt-addon` service.

If that mount remains commented out, the endpoint returns an `operator_action` command for manual restart.

## Shutdown

```bash
docker compose -f docker/docker-compose.yml down
```
