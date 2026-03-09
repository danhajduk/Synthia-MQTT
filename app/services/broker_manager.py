import crypt
import os
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


def write_embedded_compose_override(
    override_file: Path,
    broker_dir: Path,
    port: int,
    addon_service_name: str = "mqtt-addon",
) -> None:
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
                "    networks:",
                "      synthia_net:",
                "        aliases:",
                "          - mosquitto",
                "",
                f"  {addon_service_name}:",
                "    depends_on:",
                "      - mosquitto",
                "    networks:",
                "      - synthia_net",
                "",
                "networks:",
                "  synthia_net:",
                "    name: synthia_net",
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

    mosquitto_conf = broker_dir / "mosquitto.conf"
    mosquitto_conf.write_text("\n".join(conf_lines) + "\n", encoding="utf-8")
    os.chmod(mosquitto_conf, 0o644)

    if allow_anonymous:
        pwfile = broker_dir / "pwfile"
        aclfile = broker_dir / "aclfile"
        pwfile.write_text("", encoding="utf-8")
        aclfile.write_text("topic readwrite #\n", encoding="utf-8")
        os.chmod(pwfile, 0o644)
        os.chmod(aclfile, 0o644)
        return

    if not admin_user or not admin_pass:
        raise ValueError("embedded non-anonymous mode requires admin_user and admin_pass")

    pw_hash = crypt.crypt(str(admin_pass), crypt.mksalt(crypt.METHOD_SHA512))
    if not pw_hash:
        raise ValueError("failed to generate embedded broker password hash")
    pwfile = broker_dir / "pwfile"
    pwfile.write_text(f"{admin_user}:{pw_hash}\n", encoding="utf-8")
    os.chmod(pwfile, 0o644)

    acl_user = admin_user or "admin"
    aclfile = broker_dir / "aclfile"
    aclfile.write_text(f"user {acl_user}\ntopic readwrite #\n", encoding="utf-8")
    os.chmod(aclfile, 0o644)


def wait_for_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.2)
    return False
