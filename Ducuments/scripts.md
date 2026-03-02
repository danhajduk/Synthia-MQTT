# Scripts Documentation

## `scripts/rebuild.sh`

Purpose:

- Stop the stack
- Rebuild images from scratch
- Start the stack again
- Print running container status

Usage:

```bash
./scripts/rebuild.sh
```

## `scripts/validate-service-flow.sh`

Purpose:

- Verify HTTP service health endpoints.
- Verify `/api/addon/version` required fields and manifest version consistency.
- Verify `/api/addon/permissions` matches canonical manifest permissions.
- Verify retained MQTT announce and health payloads.
- Fail if announce/health retained flags are missing.
- Verify announce payload contains `addon_id`, `version`, `api_version`, and `mode`.
- Validate announce `base_url` against expected external URL.
- Optionally validate Core proxy health URL reachability.

Usage:

```bash
SERVICE_BASE_URL=http://localhost:18080 \
MQTT_HOST=10.0.0.100 \
MQTT_PORT=1883 \
MQTT_BASE_TOPIC=synthia \
EXPECTED_ANNOUNCE_BASE_URL=http://10.0.0.100:18080 \
./scripts/validate-service-flow.sh
```

## `scripts/sign-addon.sh`

Purpose:

- Package and sign addon artifact from SAS v1.1 `manifest.json`.
- Read `package_profile`, `compatibility`, and `paths` from manifest.
- Generate `dist/catalog-snippet.json` for catalog release entries.

Usage:

```bash
./scripts/sign-addon.sh
```

Optional overrides:

- `ASSET_NAME` (default `addon.tgz`)
- `ARTIFACT_URL_TEMPLATE` (supports `{version}`)
- `--artifact-url <url>` for explicit release URL

## `scripts/release-addon.sh`

Purpose:

- Build deterministic release artifact and upload to GitHub release.
- Emit `release-output.json` including `package_profile`.

Usage:

```bash
./scripts/release-addon.sh v0.1.2
```
