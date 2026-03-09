# Deployment and Packaging (Current)

Status: Active
Last Verified: 2026-03-08 (US/Pacific)

## Compose runtime

Main compose file: `docker/docker-compose.yml`

Defined service:

- `mqtt-addon` (builds from `docker/Dockerfile`)
- container env now sourced from `docker/runtime.env` via compose `env_file`
- host port mapping `18080:8080` in `docker/docker-compose.yml`
- optional override mapping `10.0.0.100:18081:8080` in `docker/docker-compose.port-override.yml`
- optional-group compose metadata includes `docker/docker-compose.mqtt-tools.yml` (manifest-declared; supervisor-driven enablement pattern)
- embedded broker optional-group compose file is `docker/docker-compose.group-broker.yml` (`id=broker`)

Image packaging note:

- `docker/Dockerfile` includes `manifest.json` in `/workspace/manifest.json` so addon contract metadata loads at startup.
- `docker/Dockerfile` copies `frontend/dist` into the image so `/ui/` is served in container runtime.
- Runtime health sampling uses an internal `HealthSnapshot` service model; API routes map it to external `AddonHealth` contract fields.

Verified UI access path:

- default compose: `http://localhost:18080/ui/`
- with port override file: `http://10.0.0.100:18081/ui/`

Notes:

- This compose file does not define `mosquitto`.
- Embedded mode writes runtime broker artifacts and desired-state intent; compose reconciliation is supervisor-driven.
- Embedded broker credential file (`runtime/broker/pwfile`) is generated as hashed Mosquitto password entries (not plaintext) with readable host bind-mount permissions.
- Managed embedded broker container name is `synthia-addon-mqtt-mosquitto`.
- Embedded runtime override generation auto-detects the addon service name from `/orchestrator/docker-compose.yml` (or `SYNTHIA_ADDON_SERVICE_NAME`) so broker `depends_on/networks` wiring remains valid across `mqtt` vs `mqtt-addon` base compose variants after reboot/reconcile.

## Bootstrap installer

Script: `scripts/bootstrap-install.sh`

Current behavior:

- Resolves latest or specific tag from GitHub releases.
- Downloads `addon.tgz` into `SynthiaAddons/services/mqtt/versions/<version>/addon.tgz`.
- Extracts `docker/docker-compose.yml` from artifact to `versions/<version>/docker-compose.yml`.
- Extracts full artifact build context into `versions/<version>/extracted/`.
- Writes `desired.json` and `runtime.json` in canonical service root.
- `desired.json` runtime intent now includes:
  - `bind_localhost` (default `false`)
  - `ports[0]` default mapping: `host=18080`, `container=8080`, `proto=tcp`
  - optional resource intent fields: `cpu`, `memory` (set via bootstrap flags/env when provided)
- Updates symlinks:
  - `SynthiaAddons/services/mqtt/current -> versions/<version>`
  - `SynthiaAddons/Synthia-MQTT -> SynthiaAddons/services/mqtt` (compatibility link)

Validation helper:

- `scripts/validate-bootstrap.sh` now checks SSAP layout invariants:
  - canonical service root path
  - presence of `desired.json` + `runtime.json`
  - `current` symlink + version artifact files (`addon.tgz`, `docker-compose.yml`, `extracted/Dockerfile`)
  - `desired.json`/`runtime.json` version fields match the `current` symlink target version
  - `desired.json` runtime port intent is present and consistent (`bind_localhost` boolean + `ports[0]` host/container/proto defaults)
  - optional runtime resource intent parity can be asserted via `EXPECTED_RUNTIME_CPU` and `EXPECTED_RUNTIME_MEMORY`
  - legacy compatibility symlink target
- `scripts/check-doc-alignment.sh` verifies local docs and implementation alignment:
  - implemented `/api/*` routes match endpoint lists in `README.md` and `docs/api.md`
  - `docs/api.md` capability list matches `app/api/addon_contract.py` capabilities
  - active docs/scripts avoid stale hardcoded version literals and keep manifest-sourced version usage
  - ownership-boundary mapping note (`backend/app/main.py` -> `app/main.py`) is present and parity-checked with golden `docs/api.md`
- optional embedded-network guard in `scripts/validate-service-flow.sh` can assert:
  - addon container is attached to expected network (`EMBEDDED_EXPECTED_NETWORK`, default `synthia_net`)
  - broker container is attached to the same network (`EMBEDDED_BROKER_CONTAINER`, default `synthia-addon-mqtt-mosquitto`)
  - broker has expected DNS alias on that network (`EMBEDDED_EXPECTED_ALIAS`, default `mosquitto`)
  - strict mode (`EMBEDDED_STRICT_BROKER_SINGLE_NETWORK=1`, default) fails validation if broker is attached to additional networks

Release gate:

- `scripts/release-addon.sh` runs `scripts/check-doc-alignment.sh --release-gate` before packaging/upload.
- release staging paths include Docker build context dependencies:
  - `manifest.json`, `docker/`, `app/`, `frontend/`, `runtime/`, `requirements.txt`
- Release-gate mode requires:
  - `docs/mismatch-report.md` `Last Verified` date matches current date
  - `docs/mismatch-report.md` `Audit Run` date matches current date
  - no finding with `Status: open` and `Ownership: local-fixable`

## Manifest and artifact

Manifest file: `manifest.json`

Verified values:

- `schema_version`: `1.1`
- `id`: `mqtt`
- `version`: sourced from `manifest.json` (`python3 -c 'import json;print(json.load(open("manifest.json","r",encoding="utf-8"))["version"])'`)
- `package_profile`: `standalone_service`
- `permissions`: `network.egress`, `mqtt.publish`, `mqtt.subscribe`
- `runtime_defaults`: `bind_localhost=false`, `ports=[{host:18080,container:8080,proto:tcp}]`
- `docker_groups`: supports addon-declared optional compose groups without hardcoded supervisor behavior

## Optional group desired/runtime state IO

Addon optional docker-group requests are persisted into desired state (no compose edits):

- desired path resolution:
  - `SYNTHIA_DESIRED_STATE_PATH` (if set)
  - `/state/desired.json` (if `/state` mount exists; container/supervisor mount)
  - `./SynthiaAddons/services/mqtt/desired.json` (if present)
  - fallback `./runtime/desired.json`
- write mode:
  - file lock (`*.lock`) + atomic replace write
  - unrelated JSON fields preserved
  - requested IDs stored under top-level `enabled_docker_groups`
  - reusable path/IO helper is centralized in `app/services/mounted_state_store.py`

Runtime feedback path resolution:

- `SYNTHIA_RUNTIME_STATE_PATH` (if set)
- `/state/runtime.json` (if `/state` mount exists; container/supervisor mount)
- `./SynthiaAddons/services/mqtt/runtime.json` (if present)
- fallback `./runtime/runtime.json`

Runtime feedback consumed by install status/UI:

- requested, active, starting, failed, and pending reconcile state.

State-write troubleshooting (container runtime):

- if desired-state save fails with `desired_state_write_blocked_missing_state_mount`, addon logs now include mount diagnostics:
  - `state_dir_exists`
  - `desired_exists`
  - `runtime_exists`
  - `desired_writable`
  - `runtime_writable`
- if `/state/desired.json` exists but is mounted read-only, addon fails with `desired_state_write_blocked_read_only_state_mount`.

Pre-reconcile asset preparation:

- selected optional groups get runtime assets prepared under `runtime/optional_groups/<group_id>/`
- deselected groups are cleaned up during reset/reconfigure

Optional docker-group pattern (addon-side):

- base-only startup:
  - addon setup/apply can complete with zero optional groups requested.
- desired-state writes:
  - addon writes intent only (`enabled_docker_groups`), never edits compose files.
- runtime-state feedback:
  - addon reads runtime reconcile feedback (`requested/active/starting/failed/pending_reconcile`) from runtime state.
- readiness:
  - full readiness requires base setup readiness and all requested `setup_required` groups active.
- supervisor responsibility:
  - supervisor reads desired intent, performs compose orchestration, and writes runtime state outcomes.

Example flow:

1. operator selects `mqtt_observer` in UI.
2. addon resolves dependencies and writes `["mqtt_tools","mqtt_observer"]` to desired state.
3. addon prepares pre-reconcile assets under `runtime/optional_groups/...`.
4. supervisor reconciles and writes runtime feedback (starting/active/failed).
5. UI shows pending/mismatch until active state converges; readiness becomes `full` only when required groups are active.
