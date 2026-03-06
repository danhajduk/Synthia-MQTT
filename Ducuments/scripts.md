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

## `scripts/validate-bootstrap.sh`

Purpose:

- Run bootstrap in demo/validation mode (`--version latest --no-open --non-interactive --addon-port 18081` by default).
- Verify addon health endpoint after bootstrap.
- Print setup UI URL.

Usage:

```bash
./scripts/validate-bootstrap.sh
```

Optional overrides:

- `ADDON_PORT` (default `18081`)
- `DEFAULT_HOST_IP` (default first value from `hostname -I`, fallback `127.0.0.1`)
- `SERVICE_BASE_URL` (default `http://$DEFAULT_HOST_IP:$ADDON_PORT`)
- `BOOTSTRAP_ARGS` (default `--version latest --no-open --non-interactive --addon-port $ADDON_PORT`)

## `scripts/bootstrap-install.sh`

Purpose:

- Fetch latest GitHub release artifact (`addon.tgz`).
- Support explicit release selection with `--version <tag|latest>` (default `latest`).
- Support idempotent re-runs:
  - skip download/layout prepare when requested version is already installed
  - use `--force` to re-download/re-prepare
- Start Docker in addon-only mode (`mqtt-addon` service only) when service startup is selected.
- Support host binding controls with `--addon-port` and `--bind` (`--bind` defaults to detected host IP).
- Wait for `healthz` readiness and open setup UI automatically after successful startup.
- Support `--no-open` and `--timeout-seconds` controls for readiness/open behavior.
- Support `--non-interactive` for automation/validation runs without terminal prompts.
- UI URL output uses full host IP by default instead of `localhost`.
- Resolve latest release using GitHub API with Releases HTML fallback if API resolution fails.
- Install into `${PWD}/SynthiaAddons/Synthia-MQTT` by default (override with `DEFAULT_INSTALL_DIR` env).
- Maintain version layout under install root: `versions/<version>/...` and `current -> versions/<version>`.
- Keep `addon.tgz` as the downloaded artifact (no tar extraction step).
- Prepare `versions/<version>/extracted` as a source-linked runtime workspace from `MAIN_ADDON_ROOT` (default: repo root).
- Create `versions/<version>/docker-compose.yml` symlink to `versions/<version>/extracted/docker/docker-compose.yml`.
- `MAIN_ADDON_ROOT` can be overridden to point bootstrap at a different local addon source tree.
- If `MAIN_ADDON_ROOT` is not set, bootstrap auto-detects from: script directory, script parent directory, current working directory, and `<candidate>/<repo-name>` variants (must contain `app/`, `docker/`, `requirements.txt`).
- Create `./SynthiaAddons/services/<addon_id> -> ./SynthiaAddons/Synthia-MQTT` symlink for SSAP `services` path compatibility.
- Write `desired.json` at addon root (`./SynthiaAddons/Synthia-MQTT/desired.json`) with full SSAP v1.0 required fields (`install_source.release.signature`, `runtime`, and `config.env` included).
- Write `runtime.json` at addon root (`./SynthiaAddons/Synthia-MQTT/runtime.json`) with deployed runtime state metadata.
- Prompt for runtime choices:
  - install local MQTT broker (Compose override)
  - Core host URL for optional registration
  - addon base URL, MQTT settings, and startup behavior
- Verify SHA256 from release checksum file when present; otherwise compute and print local digest.
- Write `.env` for compose runtime and optionally start containers.

Usage:

```bash
./scripts/bootstrap-install.sh
```

Install a specific tag:

```bash
./scripts/bootstrap-install.sh --version v0.1.5
```

Force re-install of a version:

```bash
./scripts/bootstrap-install.sh --version latest --force
```

Start with explicit bind/port:

```bash
./scripts/bootstrap-install.sh --addon-port 19080 --bind 127.0.0.1
```

Skip browser open and set readiness timeout:

```bash
./scripts/bootstrap-install.sh --no-open --timeout-seconds 90
```

Help:

```bash
./scripts/bootstrap-install.sh --help
```

## `scripts/validate-service-flow.sh`

Purpose:

- Verify HTTP service health endpoints.
- Verify `/api/addon/version` required fields and manifest version consistency.
- Verify `/api/addon/permissions` matches canonical manifest permissions.
- Verify retained MQTT announce and health payloads.
- Fail if announce/health retained flags are missing.
- Verify announce payload contains `addon_id`, `version`, `api_version`, and `mode`.
- Verify manifest `package_profile` is `standalone_service`.
- Validate canonical permission vocabulary and detect undeclared permission literals (best-effort static scan).
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

- Build and upload release artifact (`addon.tgz`) to GitHub release tag `v<version>`.
- Package backend + docker + frontend assets (including UI files).
- Auto-build frontend assets when `frontend/dist` is missing.
- Emit release snippet JSON (`release-output.json` by default).

Usage:

```bash
./scripts/release-addon.sh 0.1.6
```

## `scripts/release-addon.sh`

Purpose:

- Build deterministic release artifact and upload to GitHub release.
- Emit `release-output.json` including `package_profile`.

Usage:

```bash
./scripts/release-addon.sh v0.1.2
```
