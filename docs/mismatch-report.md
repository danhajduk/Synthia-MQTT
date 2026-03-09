# Mismatch Report: Synthia-MQTT vs /home/dan/Projects/Synthia/docs

Status: Active
Last Verified: 2026-03-08 (US/Pacific)
Audit Run: 2026-03-08 13:33 US/Pacific
Compared docs:

- `/home/dan/Projects/Synthia/docs/addons.md`
- `/home/dan/Projects/Synthia/docs/standalone-addon.md`
- `/home/dan/Projects/Synthia/docs/api.md`
- `/home/dan/Projects/Synthia/docs/store.md`
- `/home/dan/Projects/Synthia/docs/supervisor.md`
- `/home/dan/Projects/Synthia/docs/Policies/Synthia_Addon_API_and_MQTT_Standard.md`

Local docs reviewed:

- `docs/core.md`
- `docs/architecture-map.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/store.md`
- `docs/supervisor.md`

## Summary

- Total findings tracked: 3
- Open findings: 1
- Open local-fixable findings: 0
- Highest-risk open finding: stale version example in golden addons registration documentation.
- Golden standard: `/home/dan/Projects/Synthia/docs` is treated as source-of-truth for alignment.

## Findings

### Finding 1: Golden registration example version drift

Status: upstream-golden
Ownership: golden-upstream
Type: Contradictory documentation
Verification date: 2026-03-08

Affected files:

- `/home/dan/Projects/Synthia/docs/addons.md`
- `manifest.json`

Code evidence:

- `manifest.json` declares `"version": "0.2.9"`.
- `app/api/install_workflow.py` sends `MANIFEST_METADATA["version"]` in register-core payload.

Documentation evidence:

- `/home/dan/Projects/Synthia/docs/addons.md` registration curl example still shows `"version":"0.1.0"`.

Why this is a mismatch:

- The golden example can mislead operators into assuming stale registration metadata values.

Recommended correction:

- Keep Core golden docs unchanged from this repository.
- Preserve local mitigation by sourcing version dynamically from `manifest.json` in docs/scripts.
- Upstream correction request draft is maintained in `docs/upstream-golden-change-request.md`.

### Finding 2: Core API path example boundary ambiguity for addon repo

Status: mitigated-local
Ownership: local-fixable
Type: Unclear ownership boundary
Verification date: 2026-03-08

Affected files:

- `/home/dan/Projects/Synthia/docs/api.md`
- `docs/api.md`
- `app/main.py`

Code evidence:

- Addon runtime entrypoint is `app/main.py`.

Documentation evidence:

- Golden Core API doc describes route assembly in `backend/app/main.py`.
- Local `docs/api.md` now includes an ownership boundary note mapping Core path references to addon path `app/main.py`.

Why this is a mismatch:

- Golden text is correct for Core but ambiguous when read in addon repository context.

Recommended correction:

- Continue local mapping note in addon docs.
- No golden change is performed from this repository.

### Finding 3: Desired runtime port intent missing while compose publishes host port

Status: mitigated-local
Ownership: local-fixable
Type: Contradictory documentation
Verification date: 2026-03-08

Affected files:

- `/home/dan/Projects/Synthia/docs/standalone-addon.md`
- `scripts/bootstrap-install.sh`
- `docker/docker-compose.yml`
- `scripts/validate-bootstrap.sh`
- `docs/deployment.md`

Code evidence:

- `scripts/bootstrap-install.sh` now writes `desired.json` runtime with `bind_localhost` and `ports` defaults (`18080 -> 8080/tcp`) plus override flags.
- `docker/docker-compose.yml` publishes host mapping `18080:8080`.
- `scripts/validate-bootstrap.sh` now asserts `desired.runtime.bind_localhost` and `desired.runtime.ports[0]` parity.

Documentation evidence:

- Golden `standalone-addon.md` specifies that port exposure is declared through `desired.json` runtime configuration and that missing ports implies internal-only behavior.
- Local deployment docs document compose host port mappings but do not describe the current `desired.json` omission as a compatibility gap.

Why this is a mismatch:

- Previously, bootstrap desired state omitted runtime port intent while compose published host ports, creating drift against golden standalone runtime contract expectations.

Recommended correction:

- Completed locally:
  - bootstrap now emits `runtime.ports` and `runtime.bind_localhost` intent fields
  - bootstrap validation now checks runtime port intent presence/parity
  - deployment docs now document desired/runtime port intent defaults

## Ownership classification rules used in this report

- `local-fixable`: mismatch can be remediated in this repository only.
- `golden-upstream`: mismatch exists in golden docs and must be addressed upstream.
