from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.models.publish_models import HaDiscoverySensorRequest, MqttPublishResponse
from app.services.mqtt_client import MqttClientService
from app.services.policy_cache import PolicyCache
from app.services.telemetry_reporter import TelemetryReporter
from app.services.token_auth import ServiceTokenClaims


def build_ha_discovery_router(
    mqtt_service_getter: Callable[[], MqttClientService | None],
    require_discovery_scope: Callable[[], ServiceTokenClaims],
    policy_cache: PolicyCache,
    telemetry_reporter: TelemetryReporter,
) -> APIRouter:
    router = APIRouter(prefix="/api/ha/discovery", tags=["home-assistant"])

    @router.post("/sensor", response_model=MqttPublishResponse)
    def publish_sensor_discovery(
        request: HaDiscoverySensorRequest,
        claims: ServiceTokenClaims = Depends(require_discovery_scope),
    ) -> MqttPublishResponse:
        allowed, reason = policy_cache.authorize(claims, required_scope="mqtt.publish")
        if not allowed:
            raise HTTPException(status_code=403, detail=reason or "Policy denied HA discovery publish")

        mqtt_service = mqtt_service_getter()
        if mqtt_service is None:
            raise HTTPException(status_code=500, detail="MQTT service unavailable")

        topic = f"homeassistant/sensor/{request.unique_id}/config"

        payload: dict[str, str] = {
            "unique_id": request.unique_id,
            "name": request.name,
            "state_topic": request.state_topic,
        }
        if request.unit_of_measurement is not None:
            payload["unit_of_measurement"] = request.unit_of_measurement
        if request.device_class is not None:
            payload["device_class"] = request.device_class
        if request.icon is not None:
            payload["icon"] = request.icon

        ok = mqtt_service.publish(topic=topic, payload=payload, retain=True, qos=1)
        if not ok:
            raise HTTPException(status_code=500, detail="Failed to publish HA discovery payload")

        telemetry_reporter.enqueue_usage(
            consumer_addon_id=claims.sub,
            operation="mqtt.ha.discovery.publish",
            count=1,
        )
        return MqttPublishResponse(ok=True)

    return router
