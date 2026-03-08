# Store Integration Boundary (Addon Repository)

Status: Active
Last Verified: 2026-03-08 (US/Pacific)

## Scope

This document describes Store/catalog compatibility surfaces implemented in this addon repository. It does not describe Core Store internals.

## Implemented in This Repository

- Manifest metadata consumed by Store/install flows:
  - `schema_version`, `id`, `version`, `package_profile`
  - `permissions`
  - `runtime_defaults` (`bind_localhost`, `ports`)
  - `docker_groups` / `optional_docker_groups` declarations
- Bootstrap artifacts for standalone layout:
  - `SynthiaAddons/services/mqtt/desired.json`
  - `SynthiaAddons/services/mqtt/runtime.json`
  - versioned artifact layout under `SynthiaAddons/services/mqtt/versions/<version>/`
- Validation guards:
  - `scripts/validate-bootstrap.sh` checks desired/runtime contract shape
  - `scripts/check-doc-alignment.sh` verifies local docs + implementation parity for release gates

## Desired/Runtime Contract Fields Used by Addon

Desired state (`desired.json`) fields written/updated by addon workflows:

- `desired_revision`
- `enabled_docker_groups`
- compatibility mirror: `runtime.optional_docker_groups.requested`
- runtime intent defaults from bootstrap:
  - `runtime.bind_localhost`
  - `runtime.ports`
  - optional `runtime.cpu`, `runtime.memory`

Runtime state (`runtime.json`) fields read by addon workflows:

- `requested_docker_groups`
- `active_docker_groups`
- `starting_docker_groups`
- `failed_docker_groups`
- compatibility fallback: `runtime.optional_docker_groups.*`

## Ownership Boundary

- Addon-owned:
  - local API behavior and UI
  - desired intent writes for optional groups
  - runtime feedback reads for UX/status reporting
- Core Store-owned (outside this repository):
  - catalog source management
  - artifact resolution and lifecycle orchestration APIs
  - desired/runtime global reconciliation policy

## Not Developed

- Store/catalog API implementation in this repository
- Catalog signature/checksum policy enforcement in this repository
