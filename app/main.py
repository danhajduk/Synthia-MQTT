import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import require_scope
from app.api.addon_contract import ADDON_VERSION, CAPABILITIES, SSAP_API_VERSION, build_addon_contract_router
from app.api.broker_admin import build_broker_admin_router
from app.api.ha_discovery import build_ha_discovery_router
from app.api.install_workflow import build_install_workflow_router
from app.api.mqtt_publish import build_mqtt_publish_router
from app.api.mqtt_registration import build_mqtt_registration_router
from app.services.config_store import ConfigStore
from app.services.health import HealthService
from app.services.mqtt_client import MqttClientService
from app.services.policy_cache import PolicyCache
from app.services.telemetry_reporter import TelemetryReporter
from app.services.token_auth import ServiceTokenValidator
from app.services.registration_store import RegistrationStore

app = FastAPI(title="Synthia MQTT Addon", version=ADDON_VERSION.version)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

config_store = ConfigStore()
health_service = HealthService()
mqtt_service: MqttClientService | None = None
token_validator = ServiceTokenValidator(addon_id=ADDON_VERSION.addon_id)
policy_cache = PolicyCache(service_name=ADDON_VERSION.addon_id)
registration_store = RegistrationStore()
runtime_dir = Path(__file__).resolve().parents[1] / "runtime"
telemetry_reporter = TelemetryReporter(
    addon_id=ADDON_VERSION.addon_id,
    service_name=ADDON_VERSION.addon_id,
    runtime_dir=runtime_dir,
)

def reload_mqtt_service() -> None:
    global mqtt_service
    if mqtt_service is not None:
        mqtt_service.stop()

    mqtt_service = MqttClientService(
        config=config_store.get_effective_config(),
        health_service=health_service,
        capabilities=CAPABILITIES,
        addon_id=ADDON_VERSION.addon_id,
        addon_version=ADDON_VERSION.version,
        api_version=SSAP_API_VERSION,
        mode="standalone_service",
        announce_base_url=os.getenv("ANNOUNCE_BASE_URL", "http://localhost:18080"),
        policy_cache=policy_cache,
    )
    mqtt_service.start()


app.include_router(
    build_addon_contract_router(
        config_store,
        health_service,
        reload_mqtt_service,
        require_scope(token_validator, "addon.config.write"),
    )
)
app.include_router(
    build_mqtt_publish_router(
        lambda: mqtt_service,
        require_scope(token_validator, "mqtt.publish"),
        policy_cache,
        telemetry_reporter,
        config_store,
        registration_store,
    )
)
app.include_router(
    build_ha_discovery_router(
        lambda: mqtt_service,
        require_scope(token_validator, "mqtt.publish"),
        policy_cache,
        telemetry_reporter,
        config_store,
        registration_store,
    )
)
app.include_router(
    build_broker_admin_router(
        config_store,
        require_scope(token_validator, "broker.admin"),
    )
)
app.include_router(
    build_install_workflow_router(
        config_store,
        health_service,
        reload_mqtt_service,
        require_scope(token_validator, "install.apply"),
        require_scope(token_validator, "core.register"),
        require_scope(token_validator, "install.reset"),
    )
)
app.include_router(
    build_mqtt_registration_router(
        registration_store,
        config_store,
        require_scope(token_validator, "core.register"),
    )
)

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
    telemetry_reporter.start()
    reload_mqtt_service()


@app.on_event("shutdown")
def shutdown_event() -> None:
    if mqtt_service is not None:
        mqtt_service.stop()
    telemetry_reporter.stop()
