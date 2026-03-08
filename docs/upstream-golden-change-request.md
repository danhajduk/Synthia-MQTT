# Upstream Golden Documentation Change Request

Status: Proposed
Last Prepared: 2026-03-07 (US/Pacific)

## Request 1: Update registration example version in golden `addons.md`

Target file:

- `/home/dan/Projects/Synthia/docs/addons.md`

Issue summary:

- The registration curl example in golden `addons.md` currently shows `"version":"0.1.0"`.
- Current addon version is manifest-sourced and currently `0.2.0` in this repository.

Code evidence (local addon repo):

- `manifest.json` -> `"version": "0.2.0"`
- `app/api/install_workflow.py` sends `MANIFEST_METADATA["version"]` via `register_addon_endpoint(...)`

Proposed golden-doc correction:

1. Replace hardcoded registration payload version example with a manifest-sourced placeholder pattern, or
2. Update the example literal to the current release version and add a note that version must track addon manifest metadata.

Suggested wording for golden docs:

- `version` in register payload should reflect the addon service manifest/runtime version at registration time.

Owner:

- golden-upstream (`/home/dan/Projects/Synthia/docs` maintainers)

Tracking:

- Local mismatch report finding: `docs/mismatch-report.md` -> Finding 1 (`Status: upstream-golden`)
