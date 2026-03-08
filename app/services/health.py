import time
from dataclasses import dataclass


@dataclass(slots=True)
class HealthSnapshot:
    status: str
    mqtt_connected: bool
    last_error: str | None
    uptime_seconds: int


class HealthService:
    def __init__(self) -> None:
        self._started_monotonic = time.monotonic()
        self._mqtt_connected = False
        self._last_error: str | None = None
        self._offline = False

    def set_mqtt_connected(self, connected: bool) -> None:
        self._mqtt_connected = connected
        if connected:
            self._offline = False
        if connected:
            self._last_error = None

    def set_last_error(self, error: str | None) -> None:
        self._last_error = error

    def mark_offline(self) -> None:
        self._offline = True

    def snapshot(self) -> HealthSnapshot:
        status = "healthy"
        if self._offline:
            status = "offline"
        elif not self._mqtt_connected or self._last_error:
            status = "degraded"

        return HealthSnapshot(
            status=status,
            mqtt_connected=self._mqtt_connected,
            last_error=self._last_error,
            uptime_seconds=int(time.monotonic() - self._started_monotonic),
        )
