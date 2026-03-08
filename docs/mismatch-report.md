# Mismatch Report: Synthia-MQTT vs /home/dan/Projects/Synthia/docs

Status: Active
Last Verified: 2026-03-07 (US/Pacific)
Compared docs:

- `/home/dan/Projects/Synthia/docs/addons.md`
- `/home/dan/Projects/Synthia/docs/standalone-addon.md`
- `/home/dan/Projects/Synthia/docs/api.md`
- `/home/dan/Projects/Synthia/docs/Policies/Synthia_Addon_API_and_MQTT_Standard.md`

## Summary

- Total findings: 2
- Highest-risk mismatch: version example drift in golden addons registration documentation.
- Golden standard: `/home/dan/Projects/Synthia/docs` is treated as source-of-truth for alignment.

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

Recommended fix (local alignment):

- Keep Core docs unchanged (golden).
- Ensure local integration scripts/docs do not hardcode stale version examples.

## Finding 2: Core API doc backend path example does not map to this addon repo

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

Recommended fix (local alignment):

- Add local docs note mapping addon entrypoint path to Core contract expectations.

## Notes from this recheck

- Previous Finding 2 was mitigated locally by extracting full artifact build context to `versions/<version>/extracted/`.
- Previous Finding 4 was removed.
- `/home/dan/Projects/Synthia/docs/Policies/Synthia_Addon_API_and_MQTT_Standard.md` now documents `GET /api/addon/capabilities`, policy topics, and telemetry usage reporting, which aligns with current addon implementation.
- Local ownership-boundary mitigation was added in `docs/api.md` to map Core `backend/app/main.py` references to addon `app/main.py`.
