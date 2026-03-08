from datetime import datetime, timezone
from typing import Any


class LifecycleTopicHelper:
    def __init__(self, mqtt_base_topic: str, addon_id: str, qos_default: int = 1) -> None:
        base = mqtt_base_topic.strip() or "synthia"
        self._base = base.rstrip("/")
        self._addon_id = addon_id
        self._qos_default = qos_default

    @property
    def announce_topic(self) -> str:
        return f"{self._base}/addons/{self._addon_id}/announce"

    @property
    def health_topic(self) -> str:
        return f"{self._base}/addons/{self._addon_id}/health"

    @property
    def qos_default(self) -> int:
        return self._qos_default

    def announce_payload(
        self,
        *,
        base_url: str,
        version: str,
        api_version: str,
        mode: str,
        capabilities: list[str],
    ) -> dict[str, Any]:
        return {
            "id": self._addon_id,
            "addon_id": self._addon_id,
            "base_url": base_url,
            "version": version,
            "api_version": api_version,
            "mode": mode,
            "capabilities": capabilities,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def health_payload(self, mqtt_connected: bool) -> dict[str, str]:
        return {
            "status": "healthy" if mqtt_connected else "degraded",
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }

    def offline_payload(self) -> dict[str, str]:
        return {
            "status": "offline",
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
