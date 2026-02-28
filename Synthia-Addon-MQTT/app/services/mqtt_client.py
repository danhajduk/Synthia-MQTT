import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from app.services.health import HealthService

logger = logging.getLogger(__name__)


class MqttClientService:
    def __init__(
        self,
        config: dict[str, Any],
        health_service: HealthService,
        capabilities: list[str],
        announce_base_url: str = "http://mqtt-addon:8080",
    ) -> None:
        self._config = config
        self._health_service = health_service
        self._capabilities = capabilities
        self._announce_base_url = announce_base_url

        client_id = str(self._config["mqtt_client_id"])
        self._client = mqtt.Client(client_id=client_id)

        username = self._config.get("mqtt_username")
        password = self._config.get("mqtt_password")
        if username:
            self._client.username_pw_set(str(username), str(password) if password else None)

        if bool(self._config.get("mqtt_tls")):
            self._client.tls_set()

        self._health_topic = f"{self._config['mqtt_base_topic']}/addons/mqtt/health"
        self._announce_topic = f"{self._config['mqtt_base_topic']}/addons/mqtt/announce"
        self._qos = int(self._config.get("mqtt_qos", 1))

        self._client.will_set(
            topic=self._health_topic,
            payload=json.dumps(self._offline_payload()),
            qos=self._qos,
            retain=True,
        )

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        self._stop_event = threading.Event()
        self._health_thread: threading.Thread | None = None

    def start(self) -> None:
        host = str(self._config["mqtt_host"])
        port = int(self._config["mqtt_port"])

        logger.info("mqtt_connect_start", extra={"host": host, "port": port})

        self._client.connect_async(host=host, port=port, keepalive=30)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.loop_start()

        self._health_thread = threading.Thread(target=self._publish_health_forever, daemon=True)
        self._health_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=3)

        self._health_service.mark_offline()
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload: Any, retain: bool = True, qos: int = 1) -> bool:
        if isinstance(payload, (dict, list)):
            message = json.dumps(payload)
        elif isinstance(payload, str):
            message = payload
        else:
            message = json.dumps(payload)

        result = self._client.publish(topic, message, qos=qos, retain=retain)
        ok = result.rc == mqtt.MQTT_ERR_SUCCESS

        if not ok:
            error = f"Publish failed with rc={result.rc}"
            self._health_service.set_last_error(error)
            logger.error("mqtt_publish_failed", extra={"topic": topic, "rc": result.rc})

        return ok

    def _on_connect(self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: int) -> None:
        if rc == 0:
            self._health_service.set_mqtt_connected(True)
            logger.info("mqtt_connected")
            self._publish_announce()
            self._publish_health()
        else:
            error = f"MQTT connect failed with rc={rc}"
            self._health_service.set_mqtt_connected(False)
            self._health_service.set_last_error(error)
            logger.error("mqtt_connect_failed", extra={"rc": rc})

    def _on_disconnect(self, _client: mqtt.Client, _userdata: Any, rc: int) -> None:
        self._health_service.set_mqtt_connected(False)
        if rc != 0:
            error = f"MQTT disconnected unexpectedly rc={rc}"
            self._health_service.set_last_error(error)
            logger.warning("mqtt_disconnected", extra={"rc": rc})
        else:
            logger.info("mqtt_disconnected_clean")

    def _publish_announce(self) -> None:
        payload = {
            "id": "mqtt",
            "base_url": self._announce_base_url,
            "version": "0.1.0",
            "capabilities": self._capabilities,
        }
        self.publish(self._announce_topic, payload, retain=True, qos=self._qos)

    def _publish_health(self) -> None:
        payload = {
            "status": "healthy" if self._health_service.snapshot().mqtt_connected else "degraded",
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
        self.publish(self._health_topic, payload, retain=True, qos=self._qos)

    def _publish_health_forever(self) -> None:
        while not self._stop_event.is_set():
            self._publish_health()
            self._stop_event.wait(15)

    @staticmethod
    def _offline_payload() -> dict[str, str]:
        return {
            "status": "offline",
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
