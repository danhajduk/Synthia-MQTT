# API Reference (Current Implementation)

Status: Active
Last Verified: 2026-03-07 (US/Pacific)

## Base routes

- Health: `GET /healthz`
- UI root redirect: `GET /` -> `/ui`

## Ownership boundary note

Core documentation may reference route assembly in `backend/app/main.py` for the Core repository.
In this addon repository, the equivalent entrypoint is `app/main.py`.

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

`/api/addon/health` now reports setup and broker readiness details:

- `setup_state`
- `broker_mode`
- `broker_reachable`
- `broker_health`
- `direct_mqtt_supported`

Current capability values:

- `mqtt.publish`
- `mqtt.ha.discovery.publish`
- `mqtt.ha.state.publish`

## Install workflow routes

- `GET /api/install/status`
- `POST /api/install/mode`
- `POST /api/install/test-external`
- `POST /api/install/apply`
- `POST /api/install/register-core`
- `POST /api/install/reset`

`POST /api/install/mode` persists selected broker mode before apply and marks setup as `configuring`.

Implemented install modes:

- `external`: stores broker host/port/tls/credentials and reloads MQTT client
- `embedded`: writes broker files under `runtime/broker/` and attempts `docker compose up` for `mosquitto` + `mqtt-addon`

External apply validation behavior:

- `POST /api/install/test-external` records the last successful external connection test signature.
- `POST /api/install/apply` for `mode=external` requires a matching successful test first.
- override is supported with request flag `allow_unvalidated=true`.

`GET /api/install/status` now reports first-run setup readiness fields:

- `setup_state`: `unconfigured | configuring | ready | error | degraded`
- `setup_guidance`: operator-facing guidance for next action
- `direct_mqtt_supported`: expected direct MQTT support for selected mode
- `docker_sock_available`: whether Docker socket is available to manage embedded broker
- `broker_running`: current embedded broker container running status (embedded mode)

Fresh installs report `setup_state=unconfigured` until mode/config is applied.

## Broker admin route

- `POST /api/broker/restart`

Uses Docker SDK if available and updates install session verification state.

## MQTT publish routes

- `POST /api/mqtt/publish`
- `POST /api/mqtt/gateway/publish`
- `POST /api/mqtt/registrations`
- `POST /api/ha/discovery/sensor`

HA sensor discovery publishes retained payload to:

- `homeassistant/sensor/{unique_id}/config`

Lifecycle topic helpers:

- runtime now uses a shared lifecycle helper for:
  - `synthia/addons/<addon_id>/announce`
  - `synthia/addons/<addon_id>/health`
- default behavior: retained + QoS 1
- health heartbeat is periodic and announce/health are republished on reconnect

Gateway publish endpoint:

- `POST /api/mqtt/gateway/publish`
- accepts structured payload (`addon_id`, `message_type`, `payload`, optional `topic`, optional `qos`, optional `retain`)
- publishes standard JSON envelope:
  - `type`
  - `source_addon_id`
  - `timestamp`
  - `data`
- defaults:
  - `topic`: `synthia/addons/<addon_id>/<message_type>`
  - `qos`: addon config default (`mqtt_qos`)
  - `retain`: `true`

MQTT registration endpoint:

- `POST /api/mqtt/registrations` stores or updates approved addon registration with access mode:
  - `gateway_only`
  - `direct_mqtt`
  - `both`
- request flag `reprovision=true` rotates direct MQTT credential version for `direct_mqtt`/`both` registrations.
- direct modes return stable broker credentials (`username`, `password`) derived from persisted local credential metadata.
- registration now realizes effective ACL permissions:
  - separate `permissions.publish` and `permissions.subscribe`
  - publish to reserved namespaces is rejected
  - publish topics must stay in `synthia/addons/<addon_id>/...`
  - subscribe topics must be addon-owned or reserved namespace topics
- broker mode output behavior:
  - embedded mode writes generated ACL snippets under `runtime/broker/acl_generated/`
  - external mode writes operator notes under `runtime/broker/external_acl_notes/`

Operational publish routes are blocked until setup state is complete:

- when setup state is not `ready` or `degraded`, publish/discovery returns HTTP `409`

## Service-token auth for privileged operations

When `SYNTHIA_AUTH_REQUIRED=true`, privileged write operations require `Authorization: Bearer <jwt>` and scope checks:

- `POST /api/addon/config` -> scope `addon.config.write`
- `POST /api/mqtt/publish` -> scope `mqtt.publish`
- `POST /api/ha/discovery/sensor` -> scope `mqtt.publish`
- `POST /api/broker/restart` -> scope `broker.admin`
- `POST /api/install/apply` -> scope `install.apply`
- `POST /api/install/register-core` -> scope `core.register`
- `POST /api/install/reset` -> scope `install.reset`

JWT validation rules (when enabled):

- algorithm: `HS256`
- required claims: `sub`, `aud`, `jti`, `exp`, and scope claim (`scp` or `scopes`)
- expected audience: `SYNTHIA_TOKEN_AUDIENCE` (default addon id `mqtt`)
- signing key env: `SYNTHIA_JWT_SIGNING_KEY`

## Policy topic enforcement for MQTT operations

When `SYNTHIA_POLICY_ENFORCEMENT=true`, the addon subscribes to retained policy topics:

- `<mqtt_base_topic>/policy/grants/+`
- `<mqtt_base_topic>/policy/revocations/+`

Runtime behavior:

- MQTT publish/discovery requests are allowed only when the token subject has an active local grant for this service.
- Revocations are enforced from cached retained messages (`jti`, `grant_id`, or consumer addon id).
- Policy enforcement returns HTTP `403` on denied operations.

## Telemetry usage reporting

Addon runtime sends buffered best-effort usage events to Core endpoint:

- `POST /api/telemetry/usage`

Source operations currently reported:

- successful `POST /api/mqtt/publish`
- successful `POST /api/mqtt/gateway/publish`
- successful `POST /api/ha/discovery/sensor`

Reporting behavior:

- events are queued in memory and persisted to `runtime/telemetry_queue.jsonl`
- periodic flush retries are background-driven
- failed deliveries stay buffered for future retries
- runtime continues operating when Core is offline (no request-path failure on telemetry post failure)
