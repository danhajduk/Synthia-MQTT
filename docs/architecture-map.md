# Architecture Map (Current Implementation)

Status: Active
Last Verified: 2026-03-08 (US/Pacific)

## Runtime Topology

- Entrypoint: `app/main.py` (`FastAPI` app, router composition, startup/shutdown lifecycle)
- UI serving:
  - `frontend/dist` present -> static mount at `/ui`
  - `frontend/dist` missing -> `/ui` returns `503` with explicit guidance
- Health endpoint: `GET /healthz`
- Root redirect: `GET /` -> `/ui`

## Subsystems and Boundaries

### Core orchestration

- `app/main.py` wires services and routers.
- Shared runtime services:
  - config state: `app/services/config_store.py`
  - MQTT client lifecycle: `app/services/mqtt_client.py`
  - health model: `app/services/health.py`
  - telemetry buffer/flush: `app/services/telemetry_reporter.py`

### API layer

- Addon contract routes: `app/api/addon_contract.py`
- Install/setup workflow routes: `app/api/install_workflow.py`
- MQTT publish + gateway routes: `app/api/mqtt_publish.py`
- MQTT registration/topic explorer routes: `app/api/mqtt_registration.py`
- Broker admin route: `app/api/broker_admin.py`
- HA discovery routes: `app/api/ha_discovery.py`
- Auth dependency: `app/api/auth.py`

### Addon contract and manifest

- Manifest source: `manifest.json`
- Contract metadata loader: `app/api/addon_contract.py`
- Standalone profile: `package_profile=standalone_service`
- Runtime defaults declared in manifest:
  - `runtime_defaults.bind_localhost`
  - `runtime_defaults.ports`

### Store/catalog integration boundary

- This repository does not implement Store APIs.
- Compatibility surfaces implemented locally:
  - manifest metadata (`permissions`, `runtime_defaults`, `docker_groups`)
  - bootstrap `desired.json`/`runtime.json` generation under `SynthiaAddons/services/mqtt/`
  - desired/runtime schema compatibility checks in validation scripts

### Supervisor integration boundary

- Desired intent write/read model:
  - addon writes optional-group intent to `desired.json` (`enabled_docker_groups`, `desired_revision`)
  - addon reads reconcile feedback from `runtime.json` (`requested_docker_groups`, `active_docker_groups`, `starting_docker_groups`, `failed_docker_groups`)
- Compose reconciliation execution is supervisor-owned and external to this repository.

### Authentication and policy

- Optional service-token JWT validation:
  - `app/services/token_auth.py`
  - enforced via scoped dependencies on privileged write routes
- Optional policy cache/retained policy topic gating:
  - `app/services/policy_cache.py`

### Frontend UI

- Source: `frontend/`
- Build output: `frontend/dist`
- Purpose: setup/dashboard control surface for install mode, optional groups, broker state, and guidance.

## Not Developed (In This Repository)

- Core Store/catalog server implementation
- Core Supervisor process implementation
- Scheduler subsystem
- Multi-service orchestration outside this addon runtime
