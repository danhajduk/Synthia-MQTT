# Supervisor Integration Boundary (Addon Repository)

Status: Active
Last Verified: 2026-03-08 (US/Pacific)

## Scope

This document describes how this addon runtime integrates with supervisor-managed standalone deployment state. It does not document supervisor internals.

## Implemented Contract Usage

### Desired state writes (addon side)

Addon install/optional-group APIs write deployment intent through desired-state helpers:

- path resolution:
  - `SYNTHIA_DESIRED_STATE_PATH` (if set)
  - `/state/desired.json` (if `/state` mount exists; container/supervisor mount)
  - `./SynthiaAddons/services/mqtt/desired.json` (if present)
  - fallback `./runtime/desired.json`
- write behavior:
  - lock file + atomic replace
  - preserve unrelated JSON fields
- fields updated:
  - `enabled_docker_groups`
  - `desired_revision`
  - compatibility mirror under `runtime.optional_docker_groups.requested`

### Runtime state reads (addon side)

Addon status/UI reads runtime feedback:

- path resolution:
  - `SYNTHIA_RUNTIME_STATE_PATH` (if set)
  - `/state/runtime.json` (if `/state` mount exists; container/supervisor mount)
  - `./SynthiaAddons/services/mqtt/runtime.json` (if present)
  - fallback `./runtime/runtime.json`
- fields consumed:
  - `requested_docker_groups`
  - `active_docker_groups`
  - `starting_docker_groups`
  - `failed_docker_groups`
  - compatibility fallback `runtime.optional_docker_groups.*`

## Readiness and Reconcile UX Behavior

- Base setup can reach ready/degraded with no optional groups requested.
- When groups are requested, addon reports pending reconcile until runtime feedback converges.
- Readiness summary includes:
  - `readiness_state` (`not_ready | partial | full`)
  - `readiness_required_groups`
  - `readiness_missing_groups`

## Ownership Boundary

- Addon-owned:
  - desired intent emission
  - runtime feedback interpretation and operator UX
- Supervisor-owned (outside this repository):
  - compose reconciliation and process/container lifecycle
  - authoritative runtime state transitions

## Not Developed (In This Repository)

- Supervisor polling/reconcile engine
- Supervisor compose generation engine
- Supervisor runtime/state aggregation services
