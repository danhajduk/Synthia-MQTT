# Overview

This service provides a distributed MQTT addon for Synthia.

## Main Modules

- `app/api/`: HTTP APIs for addon contract, MQTT publish, and Home Assistant discovery.
- `app/services/`: Runtime logic for config persistence, health state, and MQTT client lifecycle.
- `app/models/`: Pydantic request and response models.
- `docker/`: Deployment stack with Mosquitto and addon containers.
- `scripts/`: Operational automation scripts.
