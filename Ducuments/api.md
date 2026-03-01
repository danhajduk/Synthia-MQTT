# API Module Documentation

## `app/api/addon_contract.py`

Implements required addon contract endpoints:

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`
- `GET /api/addon/config/effective` masks secret values.
- `POST /api/addon/config` persists runtime config and reloads MQTT client safely.

## `app/api/install_workflow.py`

Implements install workflow endpoints:

- `GET /api/install/status`
- `POST /api/install/test-external`
- `POST /api/install/apply`

`/api/install/apply` persists install mode config, generates embedded broker runtime files when needed, triggers broker restart flow when possible, and reconnects the MQTT client.

## `app/api/broker_admin.py`

Implements `POST /api/broker/restart` and exposes shared restart flow used by install apply.

## `app/api/mqtt_publish.py`

Implements `POST /api/mqtt/publish`:

- Validates topic.
- Delegates publish work to MQTT service.
- Returns `{ "ok": true }` on success.

## `app/api/ha_discovery.py`

Implements `POST /api/ha/discovery/sensor`:

- Builds Home Assistant sensor discovery payload.
- Publishes retained config to `homeassistant/sensor/{unique_id}/config`.
