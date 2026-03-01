# Scripts Documentation

## `scripts/rebuild.sh`

Purpose:

- Stop the stack
- Rebuild images from scratch
- Start the stack again
- Print running container status

Usage:

```bash
./scripts/rebuild.sh
```

## `scripts/validate-service-flow.sh`

Purpose:

- Verify HTTP service health endpoints.
- Verify retained MQTT announce and health payloads.
- Validate announce `base_url` against expected external URL.
- Optionally validate Core proxy health URL reachability.

Usage:

```bash
SERVICE_BASE_URL=http://localhost:18080 \
MQTT_HOST=10.0.0.100 \
MQTT_PORT=1883 \
MQTT_BASE_TOPIC=synthia \
EXPECTED_ANNOUNCE_BASE_URL=http://10.0.0.100:18080 \
./scripts/validate-service-flow.sh
```
