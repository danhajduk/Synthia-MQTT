# Services Module Documentation

## `app/services/config_store.py`

- Resolves effective config from environment defaults + runtime overrides.
- Persists overrides to `runtime/config.json`.

## `app/services/health.py`

- Tracks uptime, MQTT connection state, and last error.
- Produces health snapshots for addon health endpoint.

## `app/services/mqtt_client.py`

- Manages broker connection with reconnect behavior.
- Sets LWT offline payload.
- Publishes retained announce and periodic health messages.
- Provides generic publish method used by API endpoints.
