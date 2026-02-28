# API Module Documentation

## `app/api/addon_contract.py`

Implements required addon contract endpoints:

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`

## `app/api/mqtt_publish.py`

Implements `POST /api/mqtt/publish`:

- Validates topic.
- Delegates publish work to MQTT service.
- Returns `{ "ok": true }` on success.

## `app/api/ha_discovery.py`

Implements `POST /api/ha/discovery/sensor`:

- Builds Home Assistant sensor discovery payload.
- Publishes retained config to `homeassistant/sensor/{unique_id}/config`.
