from typing import Callable

from fastapi import APIRouter, HTTPException

from app.models.install_models import (
    ExternalConnectionConfig,
    InstallApplyRequest,
    InstallApplyResponse,
    InstallStatusResponse,
    InstallTestExternalResponse,
)
from app.services.config_store import ConfigStore
from app.services.health import HealthService
from app.services.mqtt_client import test_external_connection


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
        health = health_service.snapshot()

        return InstallStatusResponse(
            mode=mode,
            docker_sock_available=False,
            embedded_profile_required=False,
            broker_running=False,
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
        if payload.mode != "external":
            raise HTTPException(status_code=400, detail="Embedded install mode is not supported for this artifact")

        try:
            config_store.apply_install_config(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Failed to persist install config") from exc

        reload_mqtt_service()

        return InstallApplyResponse(
            ok=True,
        )

    return router
