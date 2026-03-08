# Archived Document

Status: Outdated
Replaced by: docs/core.md

Preserved for historical reference only.

---

# SSAP Operations Responsibilities

## Responsibility Split

Core (control plane):

- Writes desired state and catalog selections.
- Maintains addon registry and UI/API visibility.
- Does not own runtime container/process state.

Supervisor (orchestrator):

- Verifies artifact hash/signature before activation.
- Generates and applies runtime compose/orchestration config.
- Performs activation/rollback and writes runtime state.

Addon (data plane runtime):

- Runs service logic and local runtime behavior.
- Publishes retained announce/health over MQTT.
- Exposes required addon API contract endpoints.

## Failure Modes And Remediation

1. Signature mismatch
   - Symptom: artifact verification fails before extraction.
   - Remediation: republish correct signature for the artifact digest; confirm `publisher_key_id` and key material alignment.
2. SHA mismatch
   - Symptom: downloaded artifact hash differs from catalog digest.
   - Remediation: rebuild/re-upload artifact, update catalog digest to the exact artifact bytes, and re-run verification.
3. Compose/orchestration start failure
   - Symptom: service does not reach running state after activation.
   - Remediation: rollback `current` symlink to last known-good version, inspect Supervisor/runtime logs, fix config/image, and retry activation.
4. Missing announce payload
   - Symptom: Core registry or validators cannot discover addon endpoint.
   - Remediation: verify MQTT connectivity/credentials/base topic, confirm retained publish succeeded, and restart addon publish loop if needed.
