from typing import Callable

from fastapi import APIRouter, HTTPException

from app.models.publish_models import MqttPublishRequest, MqttPublishResponse
from app.services.mqtt_client import MqttClientService


def build_mqtt_publish_router(
    mqtt_service_getter: Callable[[], MqttClientService | None],
) -> APIRouter:
    router = APIRouter(prefix="/api/mqtt", tags=["mqtt"])

    @router.post("/publish", response_model=MqttPublishResponse)
    def publish_message(request: MqttPublishRequest) -> MqttPublishResponse:
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

        return MqttPublishResponse(ok=True)

    return router
