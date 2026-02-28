import logging

from fastapi import FastAPI

from app.api.addon_contract import CAPABILITIES, build_addon_contract_router
from app.services.config_store import ConfigStore
from app.services.health import HealthService
from app.services.mqtt_client import MqttClientService

app = FastAPI(title="Synthia MQTT Addon", version="0.1.0")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

config_store = ConfigStore()
health_service = HealthService()
mqtt_service: MqttClientService | None = None

app.include_router(build_addon_contract_router(config_store, health_service))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
def startup_event() -> None:
    global mqtt_service
    mqtt_service = MqttClientService(
        config=config_store.get_effective_config(),
        health_service=health_service,
        capabilities=CAPABILITIES,
    )
    mqtt_service.start()


@app.on_event("shutdown")
def shutdown_event() -> None:
    if mqtt_service is not None:
        mqtt_service.stop()
