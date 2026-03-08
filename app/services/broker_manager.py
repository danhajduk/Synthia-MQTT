import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOCKER_SOCKET_PATH = Path("/var/run/docker.sock")
DEFAULT_CONTAINER_NAME = "synthia-addon-mqtt-mosquitto"
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

    def docker_socket_available(self) -> bool:
        return DOCKER_SOCKET_PATH.exists()

    def broker_running(self) -> bool:
        if not DOCKER_SOCKET_PATH.exists():
            return False
        try:
            import docker
        except Exception:
            return False

        try:
            client = docker.from_env()
            container = client.containers.get(self.container_name)
            state = container.attrs.get("State") or {}
            return bool(state.get("Running"))
        except Exception:
            return False


def write_embedded_compose_override(override_file: Path, broker_dir: Path, port: int) -> None:
    override_file.parent.mkdir(parents=True, exist_ok=True)
    override_file.write_text(
        "\n".join(
            [
                "services:",
                "  mosquitto:",
                "    image: eclipse-mosquitto:2",
                "    container_name: synthia-addon-mqtt-mosquitto",
                "    restart: unless-stopped",
                "    ports:",
                f'      - "{port}:1883"',
                "    volumes:",
                f"      - {broker_dir.resolve()}/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro",
                f"      - {broker_dir.resolve()}/pwfile:/mosquitto/config/passwordfile:ro",
                f"      - {broker_dir.resolve()}/aclfile:/mosquitto/config/aclfile:ro",
                "",
                "  mqtt-addon:",
                "    depends_on:",
                "      - mosquitto",
                "",
            ]
        ),
        encoding="utf-8",
    )


def enable_embedded_broker_stack(
    repo_root: Path,
    override_file: Path,
) -> tuple[bool, str | None]:
    compose_file = repo_root / "docker" / "docker-compose.yml"
    cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_file),
        "-f",
        str(override_file),
        "up",
        "-d",
        "--remove-orphans",
        "mosquitto",
        "mqtt-addon",
    ]
    try:
        subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True, text=True)
        return True, None
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        reason = stderr or stdout or str(exc)
        return False, reason[:500]
    except Exception as exc:  # pragma: no cover
        return False, str(exc)


def write_embedded_broker_files(
    broker_dir: Path,
    embedded_config: dict[str, Any],
) -> None:
    broker_dir.mkdir(parents=True, exist_ok=True)

    allow_anonymous = bool(embedded_config.get("allow_anonymous", False))
    persistence = bool(embedded_config.get("persistence", True))
    log_type = str(embedded_config.get("log_type", "stdout"))
    port = int(embedded_config.get("port", 1883))
    admin_user = embedded_config.get("admin_user")
    admin_pass = embedded_config.get("admin_pass")

    conf_lines = [
        f"listener {port}",
        f"allow_anonymous {'true' if allow_anonymous else 'false'}",
        "",
        f"persistence {'true' if persistence else 'false'}",
        "persistence_location /mosquitto/data/",
        f"log_dest {log_type}",
    ]

    if not allow_anonymous:
        conf_lines.extend(
            [
                "password_file /mosquitto/config/passwordfile",
                "acl_file /mosquitto/config/aclfile",
            ]
        )

    (broker_dir / "mosquitto.conf").write_text("\n".join(conf_lines) + "\n", encoding="utf-8")

    if allow_anonymous:
        (broker_dir / "pwfile").write_text("", encoding="utf-8")
        (broker_dir / "aclfile").write_text("topic readwrite #\n", encoding="utf-8")
        return

    if admin_user and admin_pass:
        # Store plaintext credentials for operator tooling to convert into passwordfile if needed.
        (broker_dir / "pwfile").write_text(f"{admin_user}:{admin_pass}\n", encoding="utf-8")
    else:
        (broker_dir / "pwfile").write_text("", encoding="utf-8")

    acl_user = admin_user or "admin"
    (broker_dir / "aclfile").write_text(f"user {acl_user}\ntopic readwrite #\n", encoding="utf-8")


def wait_for_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False
