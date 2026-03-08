import os
from pathlib import Path
from shlex import quote
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.api.addon_contract import MANIFEST_METADATA
from app.models.install_models import (
    CoreRegistryRequest,
    CoreRegistryResponse,
    ExternalConnectionConfig,
    InstallApplyRequest,
    InstallApplyResponse,
    InstallModeUpdateRequest,
    InstallModeUpdateResponse,
    InstallStatusResponse,
    InstallTestExternalResponse,
)
from app.services.config_store import ConfigStore
from app.services.core_registry import register_addon_endpoint, verify_addon_endpoint
from app.services.health import HealthService
from app.services.mqtt_client import test_external_connection
from app.services.token_auth import ServiceTokenClaims


def _diagnostic_code_from_reason(ok: bool, reason: str | None) -> str:
    if ok:
        return "ok"
    if not reason:
        return "unknown_error"
    normalized = reason.lower()
    if "timed out" in normalized:
        return "timeout"
    if "refused" in normalized:
        return "connection_refused"
    if "name or service not known" in normalized or "nodename nor servname" in normalized:
        return "dns_error"
    if "mqtt connect failed with rc=" in normalized:
        return "mqtt_connect_failed"
    return "connection_error"


def _normalize_http_url(url_value: str) -> str:
    normalized = url_value.strip()
    if not normalized:
        return normalized
    if "://" not in normalized:
        return f"http://{normalized}"
    return normalized


def _setup_guidance(setup_state: str) -> str:
    if setup_state == "unconfigured":
        return "Select and save broker mode, then apply configuration in setup wizard."
    if setup_state == "configuring":
        return "Setup is in progress. Complete apply and verification steps."
    if setup_state == "ready":
        return "Setup is complete and runtime is ready."
    if setup_state == "degraded":
        return "Setup completed but broker connectivity is degraded. Check broker reachability and credentials."
    return "Setup is in error state. Review last_error and re-run setup."


def build_install_workflow_router(
    config_store: ConfigStore,
    health_service: HealthService,
    reload_mqtt_service: Callable[[], None],
    require_install_apply_scope: Callable[[], ServiceTokenClaims],
    require_core_register_scope: Callable[[], ServiceTokenClaims],
    require_install_reset_scope: Callable[[], ServiceTokenClaims],
) -> APIRouter:
    router = APIRouter(prefix="/api/install", tags=["install"])
    repo_root = Path(__file__).resolve().parents[2]

    @router.get("/status", response_model=InstallStatusResponse)
    def get_status() -> InstallStatusResponse:
        install_state = config_store.get_install_session_state()
        health = health_service.snapshot()
        last_error = health.last_error or install_state.get("last_error")
        setup_state = str(install_state.get("setup_state") or "unconfigured")

        if not bool(install_state["configured"]) and setup_state != "configuring":
            setup_state = "unconfigured"
        elif setup_state == "ready" and (not health.mqtt_connected or bool(last_error)):
            setup_state = "degraded"
        elif setup_state not in {"unconfigured", "configuring", "ready", "error", "degraded"}:
            setup_state = "error"

        direct_mqtt_supported = install_state["mode"] == "embedded"

        return InstallStatusResponse(
            mode=install_state["mode"],
            setup_state=setup_state,
            setup_guidance=_setup_guidance(setup_state),
            configured=bool(install_state["configured"]),
            verified=bool(install_state["verified"]),
            registered_to_core=bool(install_state["registered_to_core"]),
            direct_mqtt_supported=direct_mqtt_supported,
            docker_sock_available=False,
            embedded_profile_required=False,
            broker_running=False,
            mqtt_connected=health.mqtt_connected,
            last_error=last_error,
        )

    @router.post("/mode", response_model=InstallModeUpdateResponse)
    def set_mode(
        payload: InstallModeUpdateRequest,
        _claims: ServiceTokenClaims = Depends(require_install_apply_scope),
    ) -> InstallModeUpdateResponse:
        config_store.set_selected_mode(payload.mode)
        return InstallModeUpdateResponse(
            ok=True,
            mode=payload.mode,
            direct_mqtt_supported=payload.mode == "embedded",
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
        diagnostic_code = _diagnostic_code_from_reason(ok=ok, reason=reason)
        config_store.update_install_session_state(
            mode="external",
            verified=ok,
            last_error=None if ok else reason,
        )
        return InstallTestExternalResponse(ok=ok, diagnostic_code=diagnostic_code, reason=reason)

    @router.post("/apply", response_model=InstallApplyResponse)
    def apply_install(
        payload: InstallApplyRequest,
        _claims: ServiceTokenClaims = Depends(require_install_apply_scope),
    ) -> InstallApplyResponse:
        config_store.update_install_session_state(
            mode=payload.mode,
            setup_state="configuring",
            configured=False,
            verified=False,
            last_error=None,
        )
        try:
            config_store.apply_install_config(payload)
        except ValueError as exc:
            config_store.update_install_session_state(
                mode=payload.mode,
                setup_state="error",
                configured=False,
                verified=False,
                last_error=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            config_store.update_install_session_state(
                mode=payload.mode,
                setup_state="error",
                configured=False,
                verified=False,
                last_error="Failed to persist install config",
            )
            raise HTTPException(status_code=500, detail="Failed to persist install config") from exc

        if payload.mode == "external":
            reload_mqtt_service()
            config_store.update_install_session_state(
                mode="external",
                setup_state="ready",
                configured=True,
                verified=True,
                last_error=None,
            )
            return InstallApplyResponse(ok=True)

        try:
            ok, reason = config_store.apply_embedded_runtime(payload)
        except ValueError as exc:
            config_store.update_install_session_state(
                mode="embedded",
                setup_state="error",
                configured=False,
                verified=False,
                last_error=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover
            config_store.update_install_session_state(
                mode="embedded",
                setup_state="error",
                configured=False,
                verified=False,
                last_error="Failed to apply embedded broker runtime",
            )
            raise HTTPException(status_code=500, detail="Failed to apply embedded broker runtime") from exc

        if ok:
            config_store.update_install_session_state(
                mode="embedded",
                setup_state="ready",
                configured=True,
                verified=True,
                last_error=None,
            )
            return InstallApplyResponse(ok=True)

        operator_action = (
            f"cd {quote(str(repo_root))} && "
            "docker compose -f docker/docker-compose.yml "
            "-f runtime/broker/docker-compose.override.yml up -d --remove-orphans mosquitto mqtt-addon"
        )
        warning = reason
        if reason and "No such file or directory: 'docker'" in reason:
            warning = (
                "Docker CLI is not available in addon runtime. "
                "Run the operator action command on host terminal."
            )
        config_store.update_install_session_state(
            mode="embedded",
            setup_state="error",
            configured=False,
            verified=False,
            last_error=reason,
        )
        return InstallApplyResponse(
            ok=False,
            requires_operator_action=True,
            operator_action=operator_action,
            warnings=[warning] if warning else None,
        )

    @router.post("/register-core", response_model=CoreRegistryResponse)
    def register_core(
        payload: CoreRegistryRequest,
        _claims: ServiceTokenClaims = Depends(require_core_register_scope),
    ) -> CoreRegistryResponse:
        core_base_url = _normalize_http_url(payload.core_base_url or os.getenv("CORE_BASE_URL", ""))
        addon_base_url = _normalize_http_url(payload.base_url)
        addon_id = payload.addon_id.strip()
        auth_token = payload.auth_token or os.getenv("CORE_ADMIN_TOKEN")
        if not core_base_url:
            raise HTTPException(status_code=400, detail="core_base_url is required (or set CORE_BASE_URL)")
        if not addon_base_url:
            raise HTTPException(status_code=400, detail="base_url is required")

        ok, status_code, reason = register_addon_endpoint(
            core_base_url=core_base_url,
            addon_id=addon_id,
            base_url=addon_base_url,
            addon_name=MANIFEST_METADATA["name"],
            addon_version=MANIFEST_METADATA["version"],
            auth_token=auth_token,
        )
        if ok:
            verify_addon_endpoint(
                core_base_url=core_base_url,
                addon_id=addon_id,
                auth_token=auth_token,
            )
            config_store.update_install_session_state(registered_to_core=True, last_error=None)
            return CoreRegistryResponse(ok=True, status_code=status_code)

        config_store.update_install_session_state(
            registered_to_core=False,
            last_error=reason or "Core registry request failed",
        )

        if status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="Core authentication failed")
        if status_code is None:
            raise HTTPException(status_code=502, detail="Core is unreachable")
        raise HTTPException(status_code=502, detail=reason or "Core registry request failed")

    @router.post("/reset")
    def reset_install_state(
        _claims: ServiceTokenClaims = Depends(require_install_reset_scope),
    ) -> dict[str, bool | str]:
        config_store.reset_install_session_state(mode="external")
        return {"ok": True, "mode": "external"}

    return router
