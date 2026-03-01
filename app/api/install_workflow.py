from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException

from app.api.broker_admin import restart_broker_flow
from app.models.install_models import (
    ExternalConnectionConfig,
    InstallApplyRequest,
    InstallApplyResponse,
    InstallStatusResponse,
    InstallTestExternalResponse,
)
from app.services.broker_manager import BrokerManager, wait_for_port, write_embedded_broker_files
from app.services.config_store import ConfigStore
from app.services.health import HealthService
from app.services.mqtt_client import test_external_connection

OPERATOR_ACTION_UP = "docker compose -f docker/docker-compose.yml --profile embedded up -d"
OPERATOR_ACTION_RESTART = (
    "docker compose -f docker/docker-compose.yml --profile embedded restart mosquitto"
)


def build_install_workflow_router(
    config_store: ConfigStore,
    health_service: HealthService,
    reload_mqtt_service: Callable[[], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/install", tags=["install"])

    @router.get("/status", response_model=InstallStatusResponse)
    def get_status() -> InstallStatusResponse:
        install_state = config_store.get_install_state()
        mode = install_state["mode"]
        broker_manager = BrokerManager()
        docker_sock_available = broker_manager.docker_socket_available()
        embedded_port = int(install_state["embedded"]["port"])
        broker_running = wait_for_port("mosquitto", embedded_port, timeout_s=0.5)
        health = health_service.snapshot()

        return InstallStatusResponse(
            mode=mode,
            docker_sock_available=docker_sock_available,
            embedded_profile_required=(mode == "embedded" and not docker_sock_available),
            broker_running=broker_running,
            mqtt_connected=health.mqtt_connected,
            last_error=health.last_error,
        )

    @router.post("/test-external", response_model=InstallTestExternalResponse)
    def test_external(payload: ExternalConnectionConfig) -> InstallTestExternalResponse:
        ok, reason = test_external_connection(
            host=payload.host,
            port=payload.port,
            tls=payload.tls,
            username=payload.username,
            password=payload.password,
        )
        return InstallTestExternalResponse(ok=ok, reason=reason)

    @router.post("/apply", response_model=InstallApplyResponse)
    def apply_install(payload: InstallApplyRequest) -> InstallApplyResponse:
        try:
            config_store.apply_install_config(payload)
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Failed to persist install config") from exc

        warnings: list[str] = []
        requires_operator_action = False
        operator_action: str | None = None

        if payload.mode == "embedded" and payload.embedded is not None:
            try:
                write_embedded_broker_files(Path("runtime") / "broker", payload.embedded.model_dump())
            except Exception as exc:
                raise HTTPException(status_code=500, detail="Failed to generate embedded broker files") from exc

            manager = BrokerManager()
            if manager.docker_socket_available():
                restart = restart_broker_flow()
                if not bool(restart["restarted"]):
                    requires_operator_action = True
                    operator_action = str(restart["operator_action"] or OPERATOR_ACTION_RESTART)
                    warnings.append(str(restart["reason"] or "Broker restart failed"))
                elif not bool(restart["broker_ready"]):
                    warnings.append(str(restart["reason"] or "Broker did not become ready in time"))
            else:
                requires_operator_action = True
                operator_action = f"{OPERATOR_ACTION_UP}\n{OPERATOR_ACTION_RESTART}"

        reload_mqtt_service()

        return InstallApplyResponse(
            ok=True,
            requires_operator_action=requires_operator_action if requires_operator_action else None,
            operator_action=operator_action,
            warnings=warnings or None,
        )

    return router
