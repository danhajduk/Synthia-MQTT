# API Reference (Current Implementation)

Status: Active
Last Verified: 2026-03-07 (US/Pacific)

## Base routes

- Health: `GET /healthz`
- UI root redirect: `GET /` -> `/ui`

## Addon contract routes

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/version`
- `GET /api/addon/permissions`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`

`/api/addon/version` returns `{addon_id, version, api_version, manifest_version}` from manifest metadata.

`/api/addon/permissions` returns the manifest permissions array.

`/api/addon/config/effective` masks `mqtt_password`.

## Install workflow routes

- `GET /api/install/status`
- `POST /api/install/test-external`
- `POST /api/install/apply`
- `POST /api/install/register-core`
- `POST /api/install/reset`

Implemented install modes:

- `external`: stores broker host/port/tls/credentials and reloads MQTT client
- `embedded`: writes broker files under `runtime/broker/` and attempts `docker compose up` for `mosquitto` + `mqtt-addon`

## Broker admin route

- `POST /api/broker/restart`

Uses Docker SDK if available and updates install session verification state.

## MQTT publish routes

- `POST /api/mqtt/publish`
- `POST /api/ha/discovery/sensor`

HA sensor discovery publishes retained payload to:

- `homeassistant/sensor/{unique_id}/config`
