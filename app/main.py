import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.addon_contract import CAPABILITIES, build_addon_contract_router
from app.api.broker_admin import build_broker_admin_router
from app.api.ha_discovery import build_ha_discovery_router
from app.api.install_workflow import build_install_workflow_router
from app.api.mqtt_publish import build_mqtt_publish_router
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

def reload_mqtt_service() -> None:
    global mqtt_service
    if mqtt_service is not None:
        mqtt_service.stop()

    mqtt_service = MqttClientService(
        config=config_store.get_effective_config(),
        health_service=health_service,
        capabilities=CAPABILITIES,
        announce_base_url=os.getenv("ANNOUNCE_BASE_URL", "http://localhost:18080"),
    )
    mqtt_service.start()


app.include_router(build_addon_contract_router(config_store, health_service, reload_mqtt_service))
app.include_router(build_mqtt_publish_router(lambda: mqtt_service))
app.include_router(build_ha_discovery_router(lambda: mqtt_service))
app.include_router(build_broker_admin_router())
app.include_router(build_install_workflow_router(config_store, health_service, reload_mqtt_service))

ui_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if ui_dist.exists():
    app.mount("/ui", StaticFiles(directory=ui_dist, html=True), name="ui")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root_redirect() -> RedirectResponse:
    return RedirectResponse(url="/ui")


@app.on_event("startup")
def startup_event() -> None:
    reload_mqtt_service()


@app.on_event("shutdown")
def shutdown_event() -> None:
    if mqtt_service is not None:
        mqtt_service.stop()
