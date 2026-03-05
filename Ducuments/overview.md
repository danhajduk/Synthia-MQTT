# Overview

This service provides a distributed MQTT addon for Synthia.

## Main Modules

- `app/api/`: HTTP APIs for addon contract, MQTT publish, and Home Assistant discovery.
- `app/services/`: Runtime logic for config persistence, health state, and MQTT client lifecycle.
- `app/models/`: Pydantic request and response models.
- `frontend/`: Embedded setup wizard served at `/ui` when `frontend/dist` exists.
- `docker/`: Deployment stack with Mosquitto and addon containers.
- `scripts/`: Operational automation scripts.

## Addon Standard Contract

- `manifest.json` uses Synthia Addon Standard `schema_version: 1.1`.
- The addon runs with `package_profile: standalone_service`.
- Canonical permissions are `network.egress`, `mqtt.publish`, and `mqtt.subscribe`.
- Artifact signing/release scripts consume manifest `compatibility`, `package_profile`, and `paths`.

## Setup Wizard v1

- `/ui` provides a six-step setup wizard supporting both `external` broker mode and `embedded` broker mode.
- `/ui` is gated by install state: unconfigured installs open setup, configured installs open the runtime dashboard.
- Configured dashboard includes a default `Synthia MQTT` placeholder page section.
- Wizard status banner surfaces install-session flags (`mode`, `configured`, `verified`, `registered_to_core`, `last_error`) plus addon health state.
- Setup state is persisted locally for operator convenience while keeping raw secrets out of browser storage.
