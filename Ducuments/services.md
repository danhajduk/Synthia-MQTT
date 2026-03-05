# Services Module Documentation

## `app/services/config_store.py`

- Resolves effective config from environment defaults + runtime overrides.
- Persists overrides to `runtime/config.json`.
- Masks sensitive fields for effective-config API responses.
- Persists external install workflow settings and derives MQTT runtime settings.
- Persists install-session state to `runtime/install_state.json`.
- For embedded mode, writes runtime broker config files under `runtime/broker/` and applies compose override startup for `mosquitto` + `mqtt-addon`.

## `app/services/health.py`

- Tracks uptime, MQTT connection state, and last error.
- Produces health snapshots for addon health endpoint.

## `app/services/mqtt_client.py`

- Manages broker connection with reconnect behavior.
- Sets LWT offline payload.
- Publishes retained announce and periodic health messages.
- Announces `addon_id`, `version`, `api_version`, and `mode` aligned with `/api/addon/version`.
- Uses `ANNOUNCE_BASE_URL` so announce payloads expose an externally reachable service URL.
- Provides generic publish method used by API endpoints.
- Includes install-time external MQTT connectivity test helper.

## `app/services/core_registry.py`

- Posts addon service endpoint registration to Synthia Core `/api/admin/addons/registry`.
- Sends `addon_id` and externally reachable `base_url`.
- Supports optional bearer token for Core admin auth.

## `app/services/broker_manager.py`

- Handles embedded broker restart attempts with docker socket checks.
- Generates runtime embedded broker files under `runtime/broker/`.
- Generates embedded compose override file and executes compose up for embedded enablement flow.
