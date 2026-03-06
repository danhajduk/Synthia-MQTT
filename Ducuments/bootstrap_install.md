# Bootstrap Install: Current Flow vs v2 Target

## Current Flow (`scripts/bootstrap-install.sh`)

### Inputs and prompts
- Interactive-only execution (`stdin` must be a TTY).
- Prompts for:
  - install root directory
  - public host/port and `ANNOUNCE_BASE_URL`
  - MQTT base topic + QoS
  - local broker install toggle
  - external broker host/port/TLS/username/password (if local broker is not selected)
  - optional Core URL + optional Core auth token
  - start services toggle

### Version selection
- Always resolves latest release via GitHub API:
  - `GET https://api.github.com/repos/danhajduk/Synthia-MQTT/releases/latest`
- Extracts:
  - `tag_name`
  - `assets[].browser_download_url` for `addon.tgz` (or first `*.tgz`)
- No CLI `--version` support yet.
- No fallback path if API is unavailable/rate-limited.

### Download and install location
- Installs to: `${PWD}/SynthiaAddons/Synthia-MQTT` by default.
- Layout:
  - `versions/<version>/addon.tgz`
  - `versions/<version>/extracted/` (source-linked runtime workspace, not tar extraction output)
  - `versions/<version>/docker-compose.yml`
  - `current -> versions/<version>` symlink
  - `desired.json` at addon root
  - `runtime.json` at addon root
  - `./SynthiaAddons/services/<addon_id> -> ./SynthiaAddons/Synthia-MQTT` symlink
- Behavior on re-run:
  - always re-downloads selected artifact
  - always re-prepares source-linked `extracted/` layout (no tar extraction)
  - always force-updates `current` symlink

### Source-link behavior
- The script uses `MAIN_ADDON_ROOT` for source-linked runtime layout preparation.
- Default: repository root derived from script location.
- Override: set `MAIN_ADDON_ROOT=/absolute/path/to/Synthia-MQTT` before running bootstrap.

### Compose startup behavior
- Uses extracted release compose file:
  - `current/extracted/docker/docker-compose.yml`
- If local broker is selected, writes override:
  - `docker/docker-compose.bootstrap.yml`
  - defines `mosquitto` service + `mqtt-addon.depends_on`
- Startup command:
  - with local broker: `docker compose -f main -f override up -d --remove-orphans`
  - without local broker: `docker compose -f main up -d --remove-orphans`

### Runtime config output
- Writes `current/extracted/.env` with:
  - MQTT connection/env values
  - `ANNOUNCE_BASE_URL`
  - `CORE_BASE_URL`

### Core registration path
- Optional, executed after startup.
- Calls addon endpoint:
  - `POST {announce_base_url}/api/install/register-core`
  - payload includes `core_base_url`, `addon_id`, `base_url`, optional `auth_token`.


## v2 Target Flow (Task 13)

### Functional goals
1. Resolve and install latest release by default, with explicit version override support.
2. Start **addon-only** container from compose (no embedded broker in Task 13).
3. Wait for service readiness and open setup UI automatically.

### Required behavior additions
- CLI options:
  - `--version <tag|latest>` (default `latest`)
  - `--force`
  - `--addon-port`
  - `--bind`
  - `--no-open`
  - `--timeout-seconds`
- Latest resolver robustness:
  - GitHub API primary
  - Releases HTML fallback on API rate limit/failure
  - clear failure messages
- SHA256 behavior:
  - use release checksum file when available
  - otherwise compute and print checksum after download
- Idempotent install:
  - skip download/install when version is already installed (unless `--force`)
  - no-op when `current` already points to selected version
- Addon-only startup:
  - must not start broker service
  - use compose profile/service-target approach
- Readiness + UI:
  - poll health endpoint until success/timeout
  - open `/ui` via `xdg-open` (Linux) or `open` (macOS), otherwise print URL


## Breaking/Behavior Changes From Current Script

1. Broker prompt removal for Task 13 scope
- Current script asks whether to install local broker and can create/start `mosquitto`.
- v2 Task 13 explicitly forbids starting broker container.

2. New non-interactive controls
- Current script is prompt-driven and does not expose version/bind/timeout controls.
- v2 requires explicit CLI flags to support deterministic automation/validation.

3. Re-run semantics become idempotent
- Current script overwrites extraction every run.
- v2 should short-circuit on already-installed/current versions unless forced.

4. Health-gated completion
- Current script may return before service health is confirmed.
- v2 completion should include readiness polling and optional browser open.

5. Resolver and checksum hardening
- Current script assumes GitHub latest API availability and does not verify via release checksum file.
- v2 must include fallback resolution and checksum handling/reporting.
