import socket
import time
from dataclasses import dataclass
from pathlib import Path

DOCKER_SOCKET_PATH = Path("/var/run/docker.sock")
DEFAULT_CONTAINER_NAME = "synthia-mosquitto"
OPERATOR_ACTION = (
    "docker compose -f docker/docker-compose.yml --profile embedded restart mosquitto"
)


@dataclass(slots=True)
class BrokerRestartResult:
    restarted: bool
    reason: str | None = None
    operator_action: str | None = None


class BrokerManager:
    def __init__(self, container_name: str = DEFAULT_CONTAINER_NAME) -> None:
        self.container_name = container_name

    def restart_broker(self) -> BrokerRestartResult:
        if not DOCKER_SOCKET_PATH.exists():
            return BrokerRestartResult(
                restarted=False,
                reason="Docker socket not available",
                operator_action=OPERATOR_ACTION,
            )

        try:
            import docker  # Imported lazily to keep startup resilient
        except Exception as exc:  # pragma: no cover
            return BrokerRestartResult(
                restarted=False,
                reason=f"Docker SDK unavailable: {exc}",
                operator_action=OPERATOR_ACTION,
            )

        try:
            client = docker.from_env()
            container = client.containers.get(self.container_name)
            container.restart()
            return BrokerRestartResult(restarted=True)
        except Exception as exc:
            return BrokerRestartResult(
                restarted=False,
                reason=f"Docker restart failed: {exc}",
                operator_action=OPERATOR_ACTION,
            )


def wait_for_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False
