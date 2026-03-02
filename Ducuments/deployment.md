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

## Shutdown

```bash
docker compose -f docker/docker-compose.yml down
```
