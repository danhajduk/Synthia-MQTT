from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.models.registration_models import (
    MqttRegistrationInspectionResponse,
    MqttRegistrationRequest,
    MqttRegistrationResponse,
    RegistrationInspectionRecord,
    SetupCapabilitySummary,
)
from app.models.trace_models import PublishTraceLogRequest
from app.services.config_store import ConfigStore
from app.services.health import HealthService
from app.services.publish_trace_store import PublishTraceStore
from app.services.registration_store import RegistrationStore
from app.services.topic_permissions import TopicPermissionError
from app.services.token_auth import ServiceTokenClaims


def build_mqtt_registration_router(
    store: RegistrationStore,
    config_store: ConfigStore,
    health_service: HealthService,
    trace_store: PublishTraceStore,
    require_registration_scope: Callable[[], ServiceTokenClaims],
) -> APIRouter:
    router = APIRouter(prefix="/api/mqtt", tags=["mqtt-registration"])

    @router.post("/registrations", response_model=MqttRegistrationResponse)
    def upsert_registration(
        payload: MqttRegistrationRequest,
        _claims: ServiceTokenClaims = Depends(require_registration_scope),
    ) -> MqttRegistrationResponse:
        install_state = config_store.get_install_session_state()
        broker_mode = "embedded" if install_state.get("mode") == "embedded" else "external"
        try:
            record = store.upsert(payload, broker_mode=broker_mode)
        except TopicPermissionError as exc:
            trace_store.append(
                PublishTraceLogRequest(
                    operation="mqtt.registration.upsert",
                    outcome="denied",
                    addon_id=payload.addon_id.strip(),
                    caller_sub=_claims.sub,
                    detail=str(exc),
                )
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        trace_store.append(
            PublishTraceLogRequest(
                operation="mqtt.registration.upsert",
                outcome="success",
                addon_id=record.addon_id,
                caller_sub=_claims.sub,
                detail="Registration upserted",
            )
        )
        return MqttRegistrationResponse(ok=True, registration=record)

    @router.get("/registrations", response_model=MqttRegistrationInspectionResponse)
    def list_registrations(
        _claims: ServiceTokenClaims = Depends(require_registration_scope),
    ) -> MqttRegistrationInspectionResponse:
        install_state = config_store.get_install_session_state()
        broker_mode = "embedded" if install_state.get("mode") == "embedded" else "external"
        health_snapshot = health_service.snapshot()
        reachable = bool(health_snapshot.mqtt_connected)
        if install_state.get("setup_state") == "unconfigured":
            reg_health = "unknown"
        else:
            reg_health = "healthy" if reachable else "unreachable"

        setup_summary = SetupCapabilitySummary(
            setup_state=str(install_state.get("setup_state") or "unconfigured"),
            broker_mode=broker_mode,
            broker_reachable=reachable,
            direct_mqtt_supported=(broker_mode == "embedded"),
            broker_profile="embedded-managed" if broker_mode == "embedded" else "external-manual",
        )
        records = [
            RegistrationInspectionRecord(
                addon_id=record.addon_id,
                access_mode=record.access_mode,
                ha_mode=record.ha_mode,
                publish_scopes=record.permissions.publish,
                subscribe_scopes=record.permissions.subscribe,
                broker_profile=store.broker_profile_for(record.addon_id),
                health=reg_health,
                direct_mqtt_username=record.direct_mqtt.username if record.direct_mqtt is not None else None,
                updated_at=record.updated_at,
            )
            for record in store.list_registrations()
        ]
        return MqttRegistrationInspectionResponse(ok=True, setup=setup_summary, registrations=records)

    return router
