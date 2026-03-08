from typing import Callable
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.models.publish_models import (
    MqttGatewayPublishRequest,
    MqttGatewayPublishResponse,
    MqttPublishRequest,
    MqttPublishResponse,
)
from app.services.config_store import ConfigStore
from app.services.mqtt_client import MqttClientService
from app.services.policy_cache import PolicyCache
from app.services.registration_store import RegistrationStore
from app.services.telemetry_reporter import TelemetryReporter
from app.services.topic_permissions import TopicPermissionError, topic_allowed_by_scopes, validate_publish_topic
from app.services.token_auth import ServiceTokenClaims


def build_mqtt_publish_router(
    mqtt_service_getter: Callable[[], MqttClientService | None],
    require_publish_scope: Callable[[], ServiceTokenClaims],
    policy_cache: PolicyCache,
    telemetry_reporter: TelemetryReporter,
    config_store: ConfigStore,
    registration_store: RegistrationStore,
) -> APIRouter:
    router = APIRouter(prefix="/api/mqtt", tags=["mqtt"])

    @router.post("/publish", response_model=MqttPublishResponse)
    def publish_message(
        request: MqttPublishRequest,
        claims: ServiceTokenClaims = Depends(require_publish_scope),
    ) -> MqttPublishResponse:
        install_state = config_store.get_install_session_state()
        if install_state.get("setup_state") not in {"ready", "degraded"}:
            raise HTTPException(
                status_code=409,
                detail="Setup is not complete. Finish setup before using MQTT publish APIs.",
            )

        allowed, reason = policy_cache.authorize(claims, required_scope="mqtt.publish")
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Policy denied MQTT publish")

        topic = request.topic.strip()
        try:
            topic = validate_publish_topic(
                topic,
                addon_id=claims.sub if claims.sub != "anonymous" else None,
            )
        except TopicPermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        mqtt_service = mqtt_service_getter()
        if mqtt_service is None:
            raise HTTPException(status_code=500, detail="MQTT service unavailable")

        ok = mqtt_service.publish(
            topic=topic,
            payload=request.payload,
            retain=request.retain,
            qos=request.qos,
        )
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to publish MQTT message")

        telemetry_reporter.enqueue_usage(
            consumer_addon_id=claims.sub,
            operation="mqtt.publish",
            count=1,
        )
        return MqttPublishResponse(ok=True)

    @router.post("/gateway/publish", response_model=MqttGatewayPublishResponse)
    def gateway_publish(
        request: MqttGatewayPublishRequest,
        claims: ServiceTokenClaims = Depends(require_publish_scope),
    ) -> MqttGatewayPublishResponse:
        install_state = config_store.get_install_session_state()
        if install_state.get("setup_state") not in {"ready", "degraded"}:
            raise HTTPException(
                status_code=409,
                detail="Setup is not complete. Finish setup before using MQTT publish APIs.",
            )

        allowed, reason = policy_cache.authorize(claims, required_scope="mqtt.publish")
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Policy denied MQTT publish")

        registration = registration_store.get_registration(request.addon_id)
        if registration is None:
            raise HTTPException(status_code=404, detail=f"No registration found for addon_id={request.addon_id}")

        message_type = request.message_type.strip().lower()
        if not message_type:
            raise HTTPException(status_code=422, detail="message_type must not be empty")

        topic = (
            request.topic.strip()
            if request.topic and request.topic.strip()
            else f"synthia/addons/{request.addon_id.strip()}/{message_type}"
        )
        try:
            topic = validate_publish_topic(topic, addon_id=request.addon_id.strip())
        except TopicPermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not topic_allowed_by_scopes(topic, registration.permissions.publish):
            raise HTTPException(status_code=403, detail=f"Topic not allowed by registration publish scopes: {topic}")

        effective = config_store.get_effective_config()
        qos = request.qos if request.qos is not None else int(effective.get("mqtt_qos", 1))
        retain = request.retain if request.retain is not None else True
        envelope = {
            "type": message_type,
            "source_addon_id": request.addon_id.strip(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": request.payload,
        }

        mqtt_service = mqtt_service_getter()
        if mqtt_service is None:
            raise HTTPException(status_code=500, detail="MQTT service unavailable")

        ok = mqtt_service.publish(
            topic=topic,
            payload=envelope,
            retain=retain,
            qos=qos,
        )
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to publish MQTT gateway envelope")

        telemetry_reporter.enqueue_usage(
            consumer_addon_id=claims.sub,
            operation="mqtt.gateway.publish",
            count=1,
        )
        return MqttGatewayPublishResponse(ok=True, topic=topic, qos=qos, retain=retain)

    return router
