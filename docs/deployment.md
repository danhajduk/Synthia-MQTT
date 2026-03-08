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
- Downloads `addon.tgz` into `SynthiaAddons/Synthia-MQTT/versions/<version>/addon.tgz`.
- Extracts `docker/docker-compose.yml` from artifact to `versions/<version>/docker-compose.yml`.
- Writes `desired.json` with `ssap_version: 1.0` and release metadata.
- Updates symlinks:
  - `SynthiaAddons/Synthia-MQTT/current -> versions/<version>`
  - `SynthiaAddons/services/mqtt -> <install_root>`

## Manifest and artifact

Manifest file: `manifest.json`

Verified values:

- `schema_version`: `1.1`
- `id`: `mqtt`
- `version`: `0.1.9`
- `package_profile`: `standalone_service`
- `permissions`: `network.egress`, `mqtt.publish`, `mqtt.subscribe`
