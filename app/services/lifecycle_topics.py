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

    def health_payload(self, mqtt_connected: bool, heartbeat_interval_s: int) -> dict[str, str | int]:
        now = datetime.now(timezone.utc)
        fresh_until = now.timestamp() + max(heartbeat_interval_s * 2, 1)
        return {
            "status": "healthy" if mqtt_connected else "degraded",
            "last_seen": now.isoformat(),
            "fresh_until": datetime.fromtimestamp(fresh_until, tz=timezone.utc).isoformat(),
            "stale_after_s": max(heartbeat_interval_s * 2, 1),
        }

    def offline_payload(self, reason: str = "lwt") -> dict[str, str | int]:
        return {
            "status": "offline",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            "fresh_until": datetime.now(timezone.utc).isoformat(),
            "stale_after_s": 0,
            "offline_reason": reason,
        }
