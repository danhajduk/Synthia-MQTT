# Deployment Documentation

## Compose Stack

File: `docker/docker-compose.yml`

Services:

- `mqtt-addon` (`Synthia-MQTT`): FastAPI service that connects to an external broker and serves addon APIs.

Ports:

- `18080`: Addon HTTP API

## Container Deployment

```bash
MQTT_HOST=10.0.0.100 MQTT_PORT=1883 docker compose -f docker/docker-compose.yml up -d
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

## Shutdown

```bash
docker compose -f docker/docker-compose.yml down
```
