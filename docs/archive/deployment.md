# Archived Document

Status: Outdated
Replaced by: docs/core.md

Preserved for historical reference only.

---

# Deployment Documentation

## Compose Stack

File: `docker/docker-compose.yml`

Services:

- `mqtt-addon` (`Synthia-MQTT`): FastAPI service that connects to an external broker and serves addon APIs.

Ports:

- `18080`: Addon HTTP API

## Container Deployment

```bash
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 ANNOUNCE_BASE_URL=http://10.0.0.100:18080 docker compose -f docker/docker-compose.yml up -d
```

## Host Process Deployment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## systemd Deployment

```bash
sudo tee /etc/systemd/system/synthia-mqtt.service >/dev/null <<'UNIT'
[Unit]
Description=Synthia MQTT standalone service
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/dan/Projects/Synthia-MQTT
Environment=MQTT_HOST=10.0.0.100
Environment=MQTT_PORT=1883
ExecStart=/usr/bin/bash -lc 'source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8080'
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now synthia-mqtt.service
```

The service should be reachable from Synthia Core at a stable base URL (for example, `http://10.0.0.100:18080`).

## SSAP Desired/Runtime Artifacts

Canonical SSAP examples and schemas are stored in `runtime/ssap/`:

- `desired.example.json`
- `runtime.example.json`
- `desired.schema.json`
- `runtime.schema.json`

Ownership and write rules:

- Core writes `desired.json` only.
- `desired.json` writes must be atomic (write temp file then replace).
- Supervisor writes `runtime.json` only.
- Addon runtime must not mutate either file.

## Compose Generation Boundaries

- Core writes intent only (`desired.json`) and does not generate compose files.
- Supervisor generates `docker-compose.yml` from desired state and owns activation.
- Addon process must not generate or rewrite compose definitions at runtime.

Compose safety defaults for generated services:

- No privileged containers.
- No host networking.
- No host PID namespace.
- Bind HTTP/API ports to localhost unless explicitly overridden by operator policy.

Environment injection boundary:

- Service tokens and secrets must be injected through env files only.
- Secrets must not be passed via CLI flags or process arguments.

## SynthiaAddons Layout And Activation Flow

Canonical runtime layout:

```text
<SYNTHIA_ADDONS_DIR>/services/<addon_id>/
  desired.json
  runtime.json
  versions/<version>/
  current -> versions/<version>
```

Activation and rollback flow:

1. Stage artifact under `versions/<version>/addon.tgz`.
2. Verify artifact SHA-256 and publisher signature before extraction.
3. Extract to `versions/<version>/extracted/`.
4. Perform atomic symlink switch of `current` to `versions/<version>`.
5. Start/reconcile containers from active `current`.
6. If activation fails, restore previous `current` symlink and write failure state to `runtime.json`.

## Core Registry Registration

After deployment, register the endpoint in Core:

```bash
curl -X POST http://localhost:18080/api/install/register-core \
  -H "Content-Type: application/json" \
  -d '{"core_base_url":"http://10.0.0.100:3000","addon_id":"mqtt","base_url":"http://10.0.0.100:18080"}'
```

## Health/Announce/Proxy Validation

```bash
SERVICE_BASE_URL=http://localhost:18080 \
MQTT_HOST=10.0.0.100 \
EXPECTED_ANNOUNCE_BASE_URL=http://10.0.0.100:18080 \
CORE_PROXY_HEALTH_URL=http://10.0.0.100:3000/api/addons/mqtt/proxy/healthz \
./scripts/validate-service-flow.sh
```

## Artifact Signing And Release

Create signed addon outputs under `dist/` using SAS v1.1 manifest fields:

```bash
./scripts/sign-addon.sh
```

Publish a GitHub release artifact and metadata:

```bash
./scripts/release-addon.sh v0.1.2
```

Release checklist:

1. Build deterministic `addon.tgz` from the same commit/tag that will be published.
2. Compute SHA256 over artifact bytes and record the exact hex digest.
3. Sign SHA256 digest bytes using ed25519 (Option A model).
4. Confirm `publisher_key_id` matches the active publishers registry key.
5. Confirm catalog entry references the same version, artifact URL, digest, signature, and key id.
6. Verify Supervisor can stage artifact, validate hash/signature, and activate only after successful verification.

## Shutdown

```bash
docker compose -f docker/docker-compose.yml down
```
