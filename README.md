# Synthia MQTT Addon Service

Distributed MQTT addon service running as a standalone external service.

## Repository Layout

- `app/`: FastAPI application code.
- `docker/`: Compose and container build files.
- `frontend/`: Setup/dashboard UI source and build output.
- `runtime/`: Persisted runtime state and generated broker artifacts.
- `scripts/`: Bootstrap, release, and validation scripts.
- `docs/`: Active documentation and mismatch report.

## Quick Start

Bootstrap latest release artifact:

```bash
./scripts/bootstrap-install.sh --version latest
```

Bootstrap specific release tag:

```bash
ADDON_VERSION="$(python3 -c 'import json;print(json.load(open("manifest.json","r",encoding="utf-8"))["version"])')"
./scripts/bootstrap-install.sh --version "v${ADDON_VERSION}"
```

Manual compose startup:

```bash
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 docker compose -f docker/docker-compose.yml up -d
```

Optional host-port override startup:

```bash
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 docker compose -f docker/docker-compose.yml -f docker/docker-compose.port-override.yml up -d
```

Health check:

```bash
curl http://localhost:18080/healthz
```

UI:

```bash
open http://localhost:18080/ui/
```

## Implemented API Endpoints

- `GET /api/addon/meta`
- `GET /api/addon/health`
- `GET /api/addon/version`
- `GET /api/addon/permissions`
- `GET /api/addon/config/effective`
- `POST /api/addon/config`
- `GET /api/addon/capabilities`
- `GET /api/install/status`
- `POST /api/install/mode`
- `POST /api/install/test-external`
- `POST /api/install/apply`
- `POST /api/install/optional-groups`
- `POST /api/install/optional-groups/reset`
- `GET /api/install/core-base-url`
- `POST /api/install/core-base-url`
- `POST /api/install/register-core`
- `POST /api/install/reset`
- `POST /api/broker/restart`
- `POST /api/mqtt/publish`
- `POST /api/mqtt/gateway/publish`
- `GET /api/mqtt/publish-traces`
- `GET /api/mqtt/metrics`
- `GET /api/mqtt/registrations`
- `GET /api/mqtt/topic-explorer`
- `POST /api/mqtt/registrations`
- `POST /api/ha/discovery/sensor`
- `POST /api/ha/discovery/state/publish`

## First-Run Setup State

`GET /api/install/status` exposes persisted setup readiness:

- `setup_state`: `unconfigured | configuring | ready | error | degraded`
- `setup_guidance`: next-action hint for operators
- `external_direct_access_mode`: `gateway_only | manual_direct_access`
- `direct_access_summary`: explicit direct-access capability note for selected mode
- `deployment_mode`: `base_only | expanded`
- `optional_groups_supported`: optional docker groups declared by manifest metadata
- `optional_groups_requested`: selected optional docker group ids
- `optional_groups_active`: currently active optional docker group ids reported by runtime session
- `optional_groups_starting`: optional docker group ids currently starting
- `optional_groups_failed`: optional docker group ids currently marked failed
- `optional_groups_pending_reconcile`: `true` while requested groups are not fully active
- `optional_groups_reconcile_state`: `idle | waiting_for_reconcile | starting | active | failed | mixed`

Fresh installs remain `unconfigured` until broker mode/config is applied.
`POST /api/mqtt/publish` and `POST /api/ha/discovery/sensor` return `409` until setup reaches `ready` (or `degraded`).

For external broker mode, `POST /api/install/apply` requires a prior successful
`POST /api/install/test-external` for the same config unless `allow_unvalidated=true`.
`POST /api/install/mode` and `POST /api/install/apply` also accept `external_direct_access_mode`.

`POST /api/mqtt/registrations` supports `gateway_only`, `direct_mqtt`, and `both` access modes.
`GET /api/mqtt/registrations` returns registration inspection details and setup capability summary for operators.
Direct modes provision stable long-term broker credentials and support rotation with `reprovision=true`.
In external `gateway_only` mode, `direct_mqtt` and `both` registrations are rejected.
In external `manual_direct_access` mode, registrations can record `manual_direct_mqtt` mapping (`username`, optional `credential_ref`) and operators manage broker-side credentials.
Registration applies ACL/topic realization with publish/subscribe separation and reserved namespace restrictions.
Registrations also include HA mode grants (`none`, `gateway_managed`, `direct_allowed`) enforced by HA gateway helper endpoints.
Publish APIs now enforce topic validation (ownership, reserved namespace restrictions, lifecycle topic pattern checks)
and return explicit HTTP 400 errors for invalid topic contracts.
Platform topic publishes also enforce envelope schema (`type`, `source_addon_id`, `timestamp`, `data`) and message-type vocabulary.
`GET /api/mqtt/publish-traces` provides recent success/denied/error publish and provisioning trace records, including message/correlation IDs when present.
`GET /api/mqtt/topic-explorer` provides operator-facing topic summaries (reserved namespaces, addon namespaces, lifecycle topics, and registration mappings).
`GET /api/mqtt/metrics` provides publish/deny/reconnect counts, active registration count, per-addon publish summaries, and broker mode summary.

Optional docker groups can be requested from setup/dashboard UI and are persisted through `POST /api/install/optional-groups`
as desired deployment shape, while base startup remains fully functional with zero optional groups enabled.
Optional group requests are written atomically to desired state (`enabled_docker_groups`) and runtime feedback is read from `runtime.json` (`requested_docker_groups`, `active_docker_groups`, `failed_docker_groups`) to distinguish requested vs actual running groups.
`POST /api/install/optional-groups/reset` resets requested optional groups to base-only deployment intent.

Core URL edit behavior:

- `GET /api/install/core-base-url` returns the effective Core base URL used by install/register flows.
- `POST /api/install/core-base-url` persists a new Core URL after initial setup and writes desired-state `config.env.CORE_URL` so supervisor reconcile can apply the updated runtime env.
- `POST /api/install/register-core` now falls back to this persisted Core URL when `core_base_url` is omitted in the request body.
- Dashboard now includes a `Core Connection` panel to edit and save Core host:port after initial setup.

Dependency handling and readiness behavior:

- requesting a group auto-includes declared dependencies in dependency order.
- `setup_required=true` groups are treated as required-for-full-readiness when requested.
- install status exposes readiness as `not_ready | partial | full` plus required/missing group lists.

Lifecycle announce/health publishing uses shared helper logic for
`synthia/addons/<addon_id>/announce` and `synthia/addons/<addon_id>/health`
with retained + QoS 1 defaults and reconnect republish behavior.
Retained health payloads include freshness metadata (`last_seen`, `fresh_until`, `stale_after_s`) and
LWT offline publishes include `offline_reason=lwt`.

## Optional Service-Token Auth

Privileged write endpoints can enforce service-token JWT validation.

Environment variables:

- `SYNTHIA_AUTH_REQUIRED` (`true|false`, default `false`)
- `SYNTHIA_JWT_SIGNING_KEY` (required when auth is enabled)
- `SYNTHIA_TOKEN_AUDIENCE` (optional, defaults to addon id `mqtt`)

## Optional Policy Enforcement

MQTT operation gates can enforce retained policy grants/revocations.

Environment variable:

- `SYNTHIA_POLICY_ENFORCEMENT` (`true|false`, default `false`)

## Telemetry Reporting

Usage reporting to Core is buffered and best-effort (`POST /api/telemetry/usage`).

Environment variables:

- `SYNTHIA_TELEMETRY_ENABLED` (`true|false`, default `true`)
- `SYNTHIA_TELEMETRY_MAX_QUEUE` (default `500`)
- `SYNTHIA_TELEMETRY_FLUSH_INTERVAL_S` (default `15`)
- `SYNTHIA_TELEMETRY_TIMEOUT_S` (default `3`)

## Documentation Index

- `docs/core.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/mismatch-report.md`
- `docs/archive/README.md`

## Validation and Release Gates

Local docs/code alignment check:

```bash
./scripts/check-doc-alignment.sh
```

Service-flow validation now includes this alignment check before API/MQTT checks:

```bash
./scripts/validate-service-flow.sh
```

Validation now also runs regression guards:

- `tests/test_regression_guards.py` (Dockerfile manifest packaging + health snapshot contract shape)

End-to-end API flow tests:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m unittest tests/test_e2e_flows.py
```

Release packaging enforces stricter alignment gates:

```bash
./scripts/release-addon.sh <version>
```

Release-gate checks include:

- `./scripts/check-doc-alignment.sh --release-gate`
- `docs/mismatch-report.md` `Last Verified` must be refreshed for the current date.
- `docs/mismatch-report.md` `Audit Run` must be refreshed for the current date.
- open `local-fixable` mismatches must be resolved before release.

## Manifest Summary

`manifest.json` currently declares:

- `schema_version`: `1.1`
- `id`: `mqtt`
- `version`: sourced from `manifest.json` (`python3 -c 'import json;print(json.load(open("manifest.json","r",encoding="utf-8"))["version"])'`)
- `package_profile`: `standalone_service`
- permissions: `network.egress`, `mqtt.publish`, `mqtt.subscribe`
- `docker_groups`: manifest-declared optional compose groups (id/name/description/compose_file and optional dependency/setup/default flags)
