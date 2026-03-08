# Archived Document

Status: Outdated
Replaced by: docs/core.md

Preserved for historical reference only.

---

# Models Module Documentation

## `app/models/addon_models.py`

Defines models for:

- addon metadata
- addon health
- config update request
- effective config response

## `app/models/publish_models.py`

Defines models for:

- MQTT publish request and response
- Home Assistant sensor discovery request

## `app/models/install_models.py`

Defines install workflow models for:

- install status response
  - includes persisted setup session fields: `mode`, `configured`, `verified`, `registered_to_core`, `last_error`
- external broker connectivity test request/response
  - test response includes `diagnostic_code` with machine-readable outcome classification
- install apply request/response for external mode
- core registry registration request/response

Install session state persistence:

- Stored in `runtime/install_state.json`
- Canonical keys:
  - `mode`: `"embedded"` or `"external"`
  - `configured`: boolean
  - `verified`: boolean
  - `registered_to_core`: boolean
  - `last_error`: string/null
