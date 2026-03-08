# Synthia MQTT Addon Documentation (Current)

Status: Active
Last Verified: 2026-03-07 (US/Pacific)

## Scope

This document set describes the behavior currently implemented in this repository (`Synthia-MQTT`).

## Source of Truth Documents

- `docs/core.md` (this file)
- `docs/api.md`
- `docs/deployment.md`
- `docs/mismatch-report.md`

## Runtime Summary

- Runtime: FastAPI app in `app/main.py`.
- Service profile: standalone service (`manifest.json` `package_profile: standalone_service`).
- Runtime image packaging includes `manifest.json` in `/workspace/manifest.json` (required by addon contract manifest loader).
- MQTT topics published by runtime:
  - `<mqtt_base_topic>/addons/mqtt/announce` (retained)
  - `<mqtt_base_topic>/addons/mqtt/health` (retained)
- UI hosting:
  - `/ui` is served only when `frontend/dist` exists.

## Config Persistence

- Runtime overrides file: `runtime/config.json`
- Install/session state file: `runtime/install_state.json`

## Legacy Docs

Legacy repository docs from `Ducuments/` were archived to `docs/archive/` and are no longer source-of-truth.

## Verification Guards

- `scripts/check-doc-alignment.sh` is the local docs/code contract gate.
- `scripts/validate-service-flow.sh` also runs regression guard tests from `tests/test_regression_guards.py`.
