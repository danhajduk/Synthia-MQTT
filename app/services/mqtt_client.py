import json
import logging
import threading
import time
from datetime import datetime, timezone
from threading import Event
from typing import Any

import paho.mqtt.client as mqtt

from app.services.health import HealthService
from app.services.policy_cache import PolicyCache

logger = logging.getLogger(__name__)


class MqttClientService:
    def __init__(
        self,
        config: dict[str, Any],
        health_service: HealthService,
        capabilities: list[str],
        addon_id: str,
        addon_version: str,
        api_version: str,
        mode: str = "standalone_service",
        announce_base_url: str = "http://mqtt-addon:8080",
        policy_cache: PolicyCache | None = None,
    ) -> None:
        self._config = config
        self._health_service = health_service
        self._capabilities = capabilities
        self._addon_id = addon_id
        self._addon_version = addon_version
        self._api_version = api_version
        self._mode = mode
        self._announce_base_url = announce_base_url
        self._policy_cache = policy_cache

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
        self._client.on_message = self._on_message

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
            self._subscribe_policy_topics(client)
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

    def _on_message(self, _client: mqtt.Client, _userdata: Any, message: mqtt.MQTTMessage) -> None:
        if self._policy_cache is None or not self._policy_cache.enforcement_enabled():
            return

        try:
            payload_text = message.payload.decode("utf-8", errors="replace")
            self._policy_cache.ingest(message.topic, payload_text)
        except Exception as exc:  # pragma: no cover
            logger.warning("policy_message_parse_failed", extra={"error": str(exc)})

    def _publish_announce(self) -> None:
        payload = {
            "id": self._addon_id,
            "addon_id": self._addon_id,
            "base_url": self._announce_base_url,
            "version": self._addon_version,
            "api_version": self._api_version,
            "mode": self._mode,
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

    def _subscribe_policy_topics(self, client: mqtt.Client) -> None:
        if self._policy_cache is None or not self._policy_cache.enforcement_enabled():
            return
        base_topic = str(self._config.get("mqtt_base_topic", "synthia"))
        qos = int(self._config.get("mqtt_qos", 1))

        grants_topic = f"{base_topic}/policy/grants/+"
        revocations_topic = f"{base_topic}/policy/revocations/+"

        client.subscribe(grants_topic, qos=qos)
        client.subscribe(revocations_topic, qos=qos)
        logger.info("policy_topics_subscribed", extra={"grants_topic": grants_topic, "revocations_topic": revocations_topic})

    @staticmethod
    def _offline_payload() -> dict[str, str]:
        return {
            "status": "offline",
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }


def test_external_connection(
    host: str,
    port: int,
    tls: bool,
    username: str | None,
    password: str | None,
    timeout_s: float = 5.0,
) -> tuple[bool, str | None]:
    client = mqtt.Client(client_id=f"synthia-install-test-{int(time.time() * 1000)}")
    if username:
        client.username_pw_set(username, password=password)
    if tls:
        client.tls_set()

    connected = Event()
    result: dict[str, str | None] = {"reason": None}

    def on_connect(_client: mqtt.Client, _userdata: Any, _flags: Any, rc: int) -> None:
        if rc == 0:
            connected.set()
            return
        result["reason"] = f"MQTT connect failed with rc={rc}"
        connected.set()

    def on_disconnect(_client: mqtt.Client, _userdata: Any, rc: int) -> None:
        if rc != 0 and result["reason"] is None:
            result["reason"] = f"MQTT disconnected unexpectedly rc={rc}"

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(host=host, port=port, keepalive=10)
        client.loop_start()
        if not connected.wait(timeout=timeout_s):
            return False, f"Timed out connecting to {host}:{port}"
        if result["reason"] is not None:
            return False, result["reason"]
        return True, None
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            client.loop_stop()
            client.disconnect()
        except Exception:
            pass
