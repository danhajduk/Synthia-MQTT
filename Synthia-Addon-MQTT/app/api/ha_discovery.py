from typing import Callable

from fastapi import APIRouter, HTTPException

from app.models.publish_models import HaDiscoverySensorRequest, MqttPublishResponse
from app.services.mqtt_client import MqttClientService


def build_ha_discovery_router(
    mqtt_service_getter: Callable[[], MqttClientService | None],
) -> APIRouter:
    router = APIRouter(prefix="/api/ha/discovery", tags=["home-assistant"])

    @router.post("/sensor", response_model=MqttPublishResponse)
    def publish_sensor_discovery(request: HaDiscoverySensorRequest) -> MqttPublishResponse:
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

        return MqttPublishResponse(ok=True)

    return router
