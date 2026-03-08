from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.models.registration_models import (
    MqttTopicExplorerResponse,
    MqttRegistrationInspectionResponse,
    MqttRegistrationRequest,
    MqttRegistrationResponse,
    RegistrationInspectionRecord,
    RegistrationTopicMapping,
    SetupCapabilitySummary,
    TopicFamilySummary,
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
        external_direct_access_mode = str(install_state.get("external_direct_access_mode") or "gateway_only")
        try:
            if broker_mode == "external" and external_direct_access_mode == "gateway_only" and payload.access_mode in {
                "direct_mqtt",
                "both",
            }:
                raise ValueError("External gateway_only mode does not allow direct MQTT registration")
            record = store.upsert(
                payload,
                broker_mode=broker_mode,
                external_direct_access_mode=external_direct_access_mode,
            )
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
        except ValueError as exc:
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
        external_direct_access_mode = str(install_state.get("external_direct_access_mode") or "gateway_only")
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
            direct_mqtt_supported=(broker_mode == "embedded" or external_direct_access_mode == "manual_direct_access"),
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
                manual_direct_mqtt=record.manual_direct_mqtt,
                direct_mqtt_username=record.direct_mqtt.username if record.direct_mqtt is not None else None,
                updated_at=record.updated_at,
            )
            for record in store.list_registrations()
        ]
        return MqttRegistrationInspectionResponse(ok=True, setup=setup_summary, registrations=records)

    @router.get("/topic-explorer", response_model=MqttTopicExplorerResponse)
    def topic_explorer(
        _claims: ServiceTokenClaims = Depends(require_registration_scope),
    ) -> MqttTopicExplorerResponse:
        base_topic = str(config_store.get_effective_config().get("mqtt_base_topic", "synthia")).strip() or "synthia"
        reserved_namespaces = [
            f"{base_topic}/system/#",
            f"{base_topic}/core/#",
            f"{base_topic}/supervisor/#",
            f"{base_topic}/scheduler/#",
            f"{base_topic}/policy/#",
            f"{base_topic}/telemetry/#",
        ]

        records = store.list_registrations()
        mappings: list[RegistrationTopicMapping] = []
        addon_namespaces: list[str] = []
        lifecycle_topics: list[str] = []
        family_to_addons: dict[tuple[str, str], set[str]] = {}

        for record in records:
            addon_root = f"{base_topic}/addons/{record.addon_id}"
            addon_namespace = f"{addon_root}/#"
            addon_namespaces.append(addon_namespace)
            addon_lifecycle = [f"{addon_root}/announce", f"{addon_root}/health"]
            lifecycle_topics.extend(addon_lifecycle)
            mappings.append(
                RegistrationTopicMapping(
                    addon_id=record.addon_id,
                    publish_scopes=record.permissions.publish,
                    subscribe_scopes=record.permissions.subscribe,
                    lifecycle_topics=addon_lifecycle,
                )
            )

            for topic in [*record.permissions.publish, *record.permissions.subscribe, *addon_lifecycle]:
                parts = [part for part in topic.split("/") if part]
                if len(parts) < 2:
                    continue
                if len(parts) >= 3 and parts[1] == "addons":
                    family = "/".join(parts[:3]) + "/..."
                    key = (family, "addon")
                else:
                    family = "/".join(parts[:2]) + "/..."
                    key = (family, "reserved")
                if key not in family_to_addons:
                    family_to_addons[key] = set()
                family_to_addons[key].add(record.addon_id)

        topic_families = [
            TopicFamilySummary(family=family, kind=kind, registrations=sorted(addons))
            for (family, kind), addons in sorted(family_to_addons.items(), key=lambda entry: entry[0][0])
        ]
        return MqttTopicExplorerResponse(
            ok=True,
            base_topic=base_topic,
            reserved_namespaces=reserved_namespaces,
            addon_namespaces=sorted(set(addon_namespaces)),
            lifecycle_topics=sorted(set(lifecycle_topics)),
            registration_mappings=mappings,
            topic_families=topic_families,
        )

    return router
