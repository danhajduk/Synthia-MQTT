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
  - UI theme layout mirrors golden structure under `frontend/src/theme/` (`index.css`, `tokens.css`, `base.css`, `components.css`, `themes/light.css`, `themes/dark.css`).
  - Shared theme entrypoint is loaded by frontend bootstrap (`frontend/src/app.js` via `ensureSharedThemeEntry()`), not static HTML head markup.
  - Frontend build copies `frontend/src/theme/` to `frontend/dist/theme/` to preserve `/ui/theme/*` path resolution in production artifacts.
  - Theme path verification is automated with `scripts/verify-theme-paths.sh` for both source (`dev`) and build output (`prod`) checks.
  - Iframe integration verification is automated with `scripts/verify-iframe-theme.sh` (iframe class wiring, parent-theme mirroring, and iframe layout CSS rules).
  - Iframe style-language parity verification is automated with `scripts/verify-iframe-style-language.sh` (shared class mapping + fallback-scope checks).
  - UI fallback styling now resolves text, border, spacing, radius, and shadow through `--sx-*` token aliases before local fallback values.
  - Fallback token aliases also cover semantic accents (`primary/success/warning/danger`) so UI remains usable when shared semantic tokens are absent.
  - Frontend bootstrap applies shared component classes (`card`, `btn-primary|btn-secondary`, `sx-input`, `sx-status`, `sx-list|sx-list-item`) to align addon UI primitives with Core style patterns.
  - Shared fallback theme layer also includes Core-aligned list and table primitives (`sx-list*`, `sx-table`) for setup/dashboard content containers.
  - Root typography/text-rendering defaults are aligned at `:root` level and iframe mode uses constrained layout/background behavior for embedded rendering.
  - Addon-only visual overrides are scoped under `:root.core-theme-fallback` so injected Core styles remain source-of-truth when available.

## Config Persistence

- Runtime overrides file: `runtime/config.json`
- Install/session state file: `runtime/install_state.json`

## Legacy Docs

Legacy repository docs from `Documents/` were archived to `docs/archive/` and are no longer source-of-truth.

## Verification Guards

- `scripts/check-doc-alignment.sh` is the local docs/code contract gate.
- `scripts/validate-service-flow.sh` also runs regression guard tests from `tests/test_regression_guards.py`.
