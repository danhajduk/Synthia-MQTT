from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.models.publish_models import MqttPublishRequest, MqttPublishResponse
from app.services.mqtt_client import MqttClientService
from app.services.policy_cache import PolicyCache
from app.services.telemetry_reporter import TelemetryReporter
from app.services.token_auth import ServiceTokenClaims


def build_mqtt_publish_router(
    mqtt_service_getter: Callable[[], MqttClientService | None],
    require_publish_scope: Callable[[], ServiceTokenClaims],
    policy_cache: PolicyCache,
    telemetry_reporter: TelemetryReporter,
) -> APIRouter:
    router = APIRouter(prefix="/api/mqtt", tags=["mqtt"])

    @router.post("/publish", response_model=MqttPublishResponse)
    def publish_message(
        request: MqttPublishRequest,
        claims: ServiceTokenClaims = Depends(require_publish_scope),
    ) -> MqttPublishResponse:
        allowed, reason = policy_cache.authorize(claims, required_scope="mqtt.publish")
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Policy denied MQTT publish")

        topic = request.topic.strip()
        if not topic:
            raise HTTPException(status_code=422, detail="Topic must not be empty")

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

    return router
