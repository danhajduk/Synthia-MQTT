# Mismatch Report: Synthia-MQTT vs /home/dan/Projects/Synthia/docs

Status: Active
Last Verified: 2026-03-07 (US/Pacific)
Compared docs:

- `/home/dan/Projects/Synthia/docs/addons.md`
- `/home/dan/Projects/Synthia/docs/standalone-addon.md`
- `/home/dan/Projects/Synthia/docs/api.md`

## Summary

- Total findings: 4
- Highest-risk mismatch: bootstrap/deployment layout assumptions differ from standalone spec examples.

## Finding 1: API metadata version drift

Type: Contradictory documentation

Affected files:

- `/home/dan/Projects/Synthia/docs/addons.md`
- `manifest.json`

What code shows:

- Addon manifest version is `0.1.9`.

What docs say:

- Registration example in `addons.md` still shows version `0.1.0`.

Why this is a mismatch:

- Operational examples can lead to stale registration payload expectations.

Recommended fix:

- Update version examples in Core docs to neutral placeholders or current release values.

## Finding 2: Standalone artifact layout examples differ from current bootstrap flow

Type: Stale documentation

Affected files:

- `/home/dan/Projects/Synthia/docs/standalone-addon.md`
- `scripts/bootstrap-install.sh`

What code shows:

- Bootstrap stores `addon.tgz` and extracted compose file under `versions/<version>/` and writes `desired.json` at install root.
- The script does not unpack the full artifact into an `extracted/` runtime directory.

What docs say:

- Standalone spec examples emphasize an extracted build-context layout under `extracted/`.

Why this is a mismatch:

- Current addon installer behavior is artifact-retaining with targeted compose extraction only.

Recommended fix:

- Add an explicit note in standalone docs that installer layouts may be artifact-retained and compose-only extraction.

## Finding 3: Core API doc backend path example does not map to this addon repo

Type: Unclear ownership boundary

Affected files:

- `/home/dan/Projects/Synthia/docs/api.md`
- `app/main.py`

What code shows:

- This addon runtime is built from `app/main.py` in the addon repository.

What docs say:

- Core API doc references route assembly in `backend/app/main.py`.

Why this is a mismatch:

- Correct for Core repo, but ambiguous when used as addon implementation reference.

Recommended fix:

- Add a scope note in Core API docs clarifying that addon repos may use their own app entrypoint path.

## Finding 4: Registry contract minimal endpoints vs addon extended endpoints

Type: Missing documentation

Affected files:

- `/home/dan/Projects/Synthia/docs/addons.md`
- `app/api/addon_contract.py`

What code shows:

- Addon exposes additional contract endpoints (`/api/addon/version`, `/api/addon/permissions`, `/api/addon/capabilities`, `/api/addon/config/effective`).

What docs say:

- Core addons doc lists only minimal required remote endpoints (`meta`, `health`, `config`).

Why this is a mismatch:

- Current addon capability surface is broader than reference doc and may be missed by operators/integrators.

Recommended fix:

- Add an "optional standardized endpoints" section in Core docs that includes version and permissions endpoints.
