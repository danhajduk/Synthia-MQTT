# API Module Documentation

## `app/api/addon_contract.py`

Implements required addon contract endpoints:

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/version`
- `GET /api/addon/permissions`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`
- `GET /api/addon/version` returns `{ addon_id, version, api_version, manifest_version }` from `manifest.json`.
- `GET /api/addon/permissions` returns canonical static permissions from `manifest.json`.
- `GET /api/addon/config/effective` masks secret values.
- `POST /api/addon/config` persists runtime config and reloads MQTT client safely.

## `app/api/install_workflow.py`

Implements install workflow endpoints:

- `GET /api/install/status`
- `POST /api/install/test-external`
- `POST /api/install/apply`
- `POST /api/install/register-core`
- `POST /api/install/reset`

`/api/install/test-external` returns:
- `ok` (boolean)
- `diagnostic_code` (string; one of `ok`, `timeout`, `connection_refused`, `dns_error`, `mqtt_connect_failed`, `connection_error`, `unknown_error`)
- `reason` (optional diagnostic message)

`/api/install/apply` supports:
- external mode: persists external broker config and reconnects the MQTT client.
- embedded mode: persists embedded broker config, generates runtime broker files + compose override under `runtime/broker/`, and attempts `docker compose up` for `mosquitto` + `mqtt-addon`.
  - if compose apply fails, response includes `ok=false`, `requires_operator_action=true`, and an operator command hint that includes `cd <addon-root> && docker compose ...` for host execution.
  - when Docker CLI is unavailable in addon runtime, warning text is normalized to explicitly instruct host-terminal execution.
Both test/apply endpoints keep install-session state (`mode/configured/verified/last_error`) synchronized for wizard flow.
`/api/install/register-core` behavior:
- preferred Core endpoint: `POST /api/addons/registry/{addon_id}/register` with `{ base_url, name, version }`
- fallback endpoint: `POST /api/admin/addons/registry` with `{ addon_id, base_url, name, version }` when preferred route is not available
- compatibility fallback for legacy Core validation: retries legacy endpoint with `{ id, name, version, base_url }` on HTTP 422
- updates install-session `registered_to_core` and `last_error`
- maps auth failures to HTTP 401 and unreachable Core to HTTP 502
- auto-prefixes `http://` when `core_base_url` or `base_url` is provided without URL scheme
- when `auth_token` is supplied, request includes both `Authorization: Bearer <token>` and `X-Admin-Token: <token>` headers for Core auth compatibility

`/api/install/reset` behavior:
- resets persisted install-session fields to defaults
- sets default mode to `external`
- returns `{ ok: true, mode: "external" }`

Wizard UI integration:
- `/ui` setup flow is a six-step wizard for mode selection, broker details, test, apply, Core registration, and done summary.
- `/ui` gating behavior: if install state `configured=false`, setup wizard is shown; if `configured=true`, runtime dashboard is shown.
- UI persists local non-secret setup state and only stores password/token presence flags.
- status banner is sourced from install status + addon health and supports explicit setup reset via `/api/install/reset`.

## `app/api/broker_admin.py`

Implements `POST /api/broker/restart` and exposes shared restart flow used by install apply.
Restart updates install-session verification state (`verified` and `last_error`).

## `app/api/mqtt_publish.py`

Implements `POST /api/mqtt/publish`:

- Validates topic.
- Delegates publish work to MQTT service.
- Returns `{ "ok": true }` on success.

## `app/api/ha_discovery.py`

Implements `POST /api/ha/discovery/sensor`:

- Builds Home Assistant sensor discovery payload.
- Publishes retained config to `homeassistant/sensor/{unique_id}/config`.
