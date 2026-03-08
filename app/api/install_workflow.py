import os
from pathlib import Path
from shlex import quote
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.api.addon_contract import MANIFEST_METADATA, MANIFEST_OPTIONAL_DOCKER_GROUPS
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
    OptionalGroupSelectionRequest,
    OptionalGroupSelectionResponse,
)
from app.services.config_store import ConfigStore
from app.services.broker_manager import BrokerManager
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


def _setup_guidance(setup_state: str, optional_groups_pending: bool = False) -> str:
    if optional_groups_pending:
        return "Base setup is complete. Waiting for supervisor reconcile of optional docker groups."
    if setup_state == "unconfigured":
        return "Select and save broker mode, then apply configuration in setup wizard."
    if setup_state == "configuring":
        return "Setup is in progress. Complete apply and verification steps."
    if setup_state == "ready":
        return "Setup is complete and runtime is ready."
    if setup_state == "degraded":
        return "Setup completed but broker connectivity is degraded. Check broker reachability and credentials."
    return "Setup is in error state. Review last_error and re-run setup."


def _optional_reconcile_state(
    requested: list[str],
    active: list[str],
    starting: list[str],
    failed: list[str],
) -> str:
    if not requested:
        return "idle"
    if failed and not active:
        return "failed"
    if starting:
        return "starting"
    if sorted(requested) == sorted(active):
        return "active"
    if failed and active:
        return "mixed"
    return "waiting_for_reconcile"


def _direct_access_summary(mode: str, external_direct_access_mode: str) -> str:
    if mode == "embedded":
        return "Embedded broker supports managed direct MQTT credentials."
    if external_direct_access_mode == "manual_direct_access":
        return "External broker direct access is manual-only: operator must provision broker users and record mapping."
    return "External broker is gateway-only: direct MQTT credentials are not provisioned."


def _external_signature(payload: ExternalConnectionConfig) -> str:
    return "|".join(
        [
            payload.host.strip(),
            str(payload.port),
            "1" if payload.tls else "0",
            payload.username or "",
            payload.password or "",
        ]
    )


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
    supported_optional_groups = MANIFEST_OPTIONAL_DOCKER_GROUPS
    supported_optional_group_ids = {group.id for group in supported_optional_groups}

    @router.get("/status", response_model=InstallStatusResponse)
    def get_status() -> InstallStatusResponse:
        install_state = config_store.get_install_session_state()
        health = health_service.snapshot()
        last_error = health.last_error or install_state.get("last_error")
        setup_state = str(install_state.get("setup_state") or "unconfigured")
        broker_manager = BrokerManager()
        docker_sock_available = broker_manager.docker_socket_available()
        broker_running = broker_manager.broker_running() if install_state["mode"] == "embedded" else False
        external_direct_access_mode = str(install_state.get("external_direct_access_mode") or "gateway_only")
        if external_direct_access_mode not in {"gateway_only", "manual_direct_access"}:
            external_direct_access_mode = "gateway_only"

        if not bool(install_state["configured"]) and setup_state != "configuring":
            setup_state = "unconfigured"
        elif setup_state == "ready" and (not health.mqtt_connected or bool(last_error)):
            setup_state = "degraded"
        elif setup_state not in {"unconfigured", "configuring", "ready", "error", "degraded"}:
            setup_state = "error"

        direct_mqtt_supported = install_state["mode"] == "embedded" or (
            install_state["mode"] == "external" and external_direct_access_mode == "manual_direct_access"
        )
        optional_groups_requested = [
            str(group_id) for group_id in config_store.get_desired_optional_groups() if str(group_id) in supported_optional_group_ids
        ]
        runtime_optional_groups = config_store.get_runtime_optional_groups_feedback()
        runtime_requested = [
            str(group_id)
            for group_id in runtime_optional_groups.get("requested", [])
            if str(group_id) in supported_optional_group_ids
        ]
        if runtime_requested:
            optional_groups_requested = runtime_requested
        optional_groups_active = [
            str(group_id)
            for group_id in runtime_optional_groups.get("active", [])
            if str(group_id) in supported_optional_group_ids
        ]
        optional_groups_starting = [
            str(group_id)
            for group_id in runtime_optional_groups.get("starting", [])
            if str(group_id) in supported_optional_group_ids
        ]
        optional_groups_failed = [
            str(group_id)
            for group_id in runtime_optional_groups.get("failed", [])
            if str(group_id) in supported_optional_group_ids
        ]
        pending_from_runtime = runtime_optional_groups.get("pending_reconcile")
        optional_groups_pending_reconcile = (
            bool(pending_from_runtime)
            if isinstance(pending_from_runtime, bool)
            else sorted(optional_groups_requested) != sorted(optional_groups_active)
        )
        optional_groups_reconcile_state = _optional_reconcile_state(
            requested=optional_groups_requested,
            active=optional_groups_active,
            starting=optional_groups_starting,
            failed=optional_groups_failed,
        )
        deployment_mode = "expanded" if optional_groups_active else "base_only"

        return InstallStatusResponse(
            mode=install_state["mode"],
            external_direct_access_mode=external_direct_access_mode,
            direct_access_summary=_direct_access_summary(install_state["mode"], external_direct_access_mode),
            setup_state=setup_state,
            setup_guidance=_setup_guidance(setup_state, optional_groups_pending=optional_groups_pending_reconcile),
            configured=bool(install_state["configured"]),
            verified=bool(install_state["verified"]),
            registered_to_core=bool(install_state["registered_to_core"]),
            direct_mqtt_supported=direct_mqtt_supported,
            docker_sock_available=docker_sock_available,
            embedded_profile_required=False,
            broker_running=broker_running,
            mqtt_connected=health.mqtt_connected,
            last_error=last_error,
            optional_groups_supported=supported_optional_groups,
            optional_groups_requested=optional_groups_requested,
            optional_groups_active=optional_groups_active,
            optional_groups_starting=optional_groups_starting,
            optional_groups_failed=optional_groups_failed,
            optional_groups_pending_reconcile=optional_groups_pending_reconcile,
            deployment_mode=deployment_mode,
            optional_groups_reconcile_state=optional_groups_reconcile_state,
        )

    @router.post("/optional-groups", response_model=OptionalGroupSelectionResponse)
    def set_optional_groups(
        payload: OptionalGroupSelectionRequest,
        _claims: ServiceTokenClaims = Depends(require_install_apply_scope),
    ) -> OptionalGroupSelectionResponse:
        updated = config_store.set_requested_optional_groups(
            requested_group_ids=payload.requested_group_ids,
            supported_group_ids=supported_optional_group_ids,
        )
        requested = [str(group_id) for group_id in updated.get("optional_groups_requested", []) if str(group_id)]
        runtime_feedback = config_store.get_runtime_optional_groups_feedback()
        active = [str(group_id) for group_id in runtime_feedback.get("active", []) if str(group_id)]
        pending_from_runtime = runtime_feedback.get("pending_reconcile")
        return OptionalGroupSelectionResponse(
            ok=True,
            requested_group_ids=requested,
            pending_reconcile=bool(pending_from_runtime) if isinstance(pending_from_runtime, bool) else sorted(requested) != sorted(active),
        )

    @router.post("/mode", response_model=InstallModeUpdateResponse)
    def set_mode(
        payload: InstallModeUpdateRequest,
        _claims: ServiceTokenClaims = Depends(require_install_apply_scope),
    ) -> InstallModeUpdateResponse:
        updated = config_store.set_selected_mode(
            payload.mode,
            external_direct_access_mode=payload.external_direct_access_mode,
        )
        return InstallModeUpdateResponse(
            ok=True,
            mode=payload.mode,
            direct_mqtt_supported=payload.mode == "embedded" or (
                payload.mode == "external" and updated.get("external_direct_access_mode") == "manual_direct_access"
            ),
            external_direct_access_mode=str(updated.get("external_direct_access_mode") or "gateway_only"),
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
        signature = _external_signature(payload)
        config_store.update_install_session_state(
            mode="external",
            setup_state="configuring",
            verified=ok,
            last_error=None if ok else reason,
            external_test_ok=ok,
            external_test_signature=signature if ok else None,
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
            external_direct_access_mode=payload.external_direct_access_mode,
            last_error=None,
        )
        if payload.mode == "external" and not payload.allow_unvalidated:
            install_state = config_store.get_install_session_state()
            expected_signature = install_state.get("external_test_signature")
            tested_ok = bool(install_state.get("external_test_ok"))
            request_external = payload.external
            if request_external is None:
                raise HTTPException(status_code=400, detail="external config is required when mode is external")
            if not tested_ok or expected_signature != _external_signature(request_external):
                raise HTTPException(
                    status_code=400,
                    detail="External config must pass /api/install/test-external before apply.",
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
                external_direct_access_mode=payload.external_direct_access_mode,
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
            reload_mqtt_service()
            config_store.update_install_session_state(
                mode="embedded",
                setup_state="ready",
                configured=True,
                verified=True,
                external_direct_access_mode=payload.external_direct_access_mode,
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
