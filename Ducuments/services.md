# Services Module Documentation

## `app/services/config_store.py`

- Resolves effective config from environment defaults + runtime overrides.
- Persists overrides to `runtime/config.json`.
- Masks sensitive fields for effective-config API responses.
- Persists external install workflow settings and derives MQTT runtime settings.

## `app/services/health.py`

- Tracks uptime, MQTT connection state, and last error.
- Produces health snapshots for addon health endpoint.

## `app/services/mqtt_client.py`

- Manages broker connection with reconnect behavior.
- Sets LWT offline payload.
- Publishes retained announce and periodic health messages.
- Provides generic publish method used by API endpoints.
- Includes install-time external MQTT connectivity test helper.

## `app/services/core_registry.py`

- Posts addon service endpoint registration to Synthia Core `/api/admin/addons/registry`.
- Sends `addon_id` and externally reachable `base_url`.
- Supports optional bearer token for Core admin auth.

## `app/services/broker_manager.py`

- Handles embedded broker restart attempts with docker socket checks.
- Generates runtime embedded broker files under `runtime/broker/`.
