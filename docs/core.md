# Synthia MQTT Addon Documentation (Current)

Status: Active
Last Verified: 2026-03-08 (US/Pacific)

## Scope

This document set describes the behavior currently implemented in this repository (`Synthia-MQTT`).

## Documentation Index

- `docs/core.md` (index and scope)
- `docs/architecture-map.md` (code-verified subsystem map)
- `docs/api.md` (implemented HTTP routes and contracts)
- `docs/deployment.md` (compose/bootstrap/release behavior)
- `docs/store.md` (addon-side Store integration boundary)
- `docs/supervisor.md` (addon-side Supervisor integration boundary)
- `docs/mismatch-report.md` (local vs golden drift tracking)
- `docs/upstream-golden-change-request.md` (open upstream correction requests)
- `docs/archive/README.md` (archived legacy docs)

## Subsystem Coverage (Code-Verified)

- Core orchestration: Implemented (`app/main.py`, service wiring, startup/shutdown lifecycle)
- API layer: Implemented (`app/api/*.py`)
- Addon system: Implemented (manifest metadata + addon contract routes + standalone profile)
- Store/catalog integration: Implemented boundary only (manifest/runtime intent compatibility; no local Store API implementation)
- Scheduler: Not developed in this repository
- Authentication: Implemented optional service-token JWT for privileged write routes
- Frontend UI: Implemented (`frontend/` static setup/dashboard shell served on `/ui`)
- Supervisor integration: Implemented boundary via `desired.json` writes and `runtime.json` feedback consumption

## Runtime Summary

- Runtime: FastAPI app in `app/main.py`.
- Service profile: standalone service (`manifest.json` `package_profile: standalone_service`).
- Runtime image packaging includes `manifest.json` in `/workspace/manifest.json` (required by addon contract manifest loader).
- MQTT topics published by runtime:
  - `<mqtt_base_topic>/addons/mqtt/announce` (retained)
  - `<mqtt_base_topic>/addons/mqtt/health` (retained)
- UI hosting:
  - `/ui` is served only when `frontend/dist` exists.
  - UI styles use addon-owned fallback tokens and auto-adopt Core theme tokens/classes when injected into iframe document.

## Config Persistence

- Runtime overrides file: `runtime/config.json`
- Install/session state file: `runtime/install_state.json`

## Legacy Docs

Legacy repository docs from `Documents/` were archived to `docs/archive/` and are no longer source-of-truth.

## Verification Guards

- `scripts/check-doc-alignment.sh` is the local docs/code contract gate.
- `scripts/validate-service-flow.sh` also runs regression guard tests from `tests/test_regression_guards.py`.
