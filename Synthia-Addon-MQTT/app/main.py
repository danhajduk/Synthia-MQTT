from fastapi import FastAPI

from app.api.addon_contract import build_addon_contract_router
from app.services.config_store import ConfigStore
from app.services.health import HealthService

app = FastAPI(title="Synthia MQTT Addon", version="0.1.0")

config_store = ConfigStore()
health_service = HealthService()

app.include_router(build_addon_contract_router(config_store, health_service))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
