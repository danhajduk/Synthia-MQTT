# Deployment and Packaging (Current)

Status: Active
Last Verified: 2026-03-07 (US/Pacific)

## Compose runtime

Main compose file: `docker/docker-compose.yml`

Defined service:

- `mqtt-addon` (builds from `docker/Dockerfile`)

Notes:

- This compose file does not define `mosquitto`.
- Embedded mode relies on runtime override generation and host Docker compose execution path.

## Bootstrap installer

Script: `scripts/bootstrap-install.sh`

Current behavior:

- Resolves latest or specific tag from GitHub releases.
- Downloads `addon.tgz` into `SynthiaAddons/services/mqtt/versions/<version>/addon.tgz`.
- Extracts `docker/docker-compose.yml` from artifact to `versions/<version>/docker-compose.yml`.
- Extracts full artifact build context into `versions/<version>/extracted/`.
- Writes `desired.json` and `runtime.json` in canonical service root.
- Updates symlinks:
  - `SynthiaAddons/services/mqtt/current -> versions/<version>`
  - `SynthiaAddons/Synthia-MQTT -> SynthiaAddons/services/mqtt` (compatibility link)

Validation helper:

- `scripts/validate-bootstrap.sh` now checks SSAP layout invariants:
  - canonical service root path
  - presence of `desired.json` + `runtime.json`
  - `current` symlink + version artifact files (`addon.tgz`, `docker-compose.yml`, `extracted/Dockerfile`)
  - `desired.json`/`runtime.json` version fields match the `current` symlink target version
  - legacy compatibility symlink target

## Manifest and artifact

Manifest file: `manifest.json`

Verified values:

- `schema_version`: `1.1`
- `id`: `mqtt`
- `version`: sourced from `manifest.json` (`python3 -c 'import json;print(json.load(open("manifest.json","r",encoding="utf-8"))["version"])'`)
- `package_profile`: `standalone_service`
- `permissions`: `network.egress`, `mqtt.publish`, `mqtt.subscribe`
