from typing import Callable

from fastapi import APIRouter, HTTPException

from app.models.addon_models import (
    AddonConfigEffective,
    AddonConfigUpdate,
    AddonHealth,
    AddonMeta,
)
from app.services.config_store import ConfigStore
from app.services.health import HealthService

META = AddonMeta(
    id="mqtt",
    name="MQTT Service",
    version="0.1.0",
    description="Distributed MQTT and HA discovery service",
)

CAPABILITIES = [
    "mqtt.publish",
    "mqtt.ha_discovery.publish",
    "mqtt.ha_state.publish",
]


def build_addon_contract_router(
    config_store: ConfigStore,
    health_service: HealthService,
    apply_runtime_config: Callable[[], None],
) -> APIRouter:
    router = APIRouter(prefix="/api/addon", tags=["addon"])

    @router.get("/meta", response_model=AddonMeta)
    def get_meta() -> AddonMeta:
        return META

    @router.get("/health", response_model=AddonHealth)
    def get_health() -> AddonHealth:
        return health_service.snapshot()

    @router.get("/config/effective", response_model=AddonConfigEffective)
    def get_effective_config() -> AddonConfigEffective:
        return AddonConfigEffective(**config_store.get_effective_config(mask_secrets=True))

    @router.post("/config", response_model=AddonConfigEffective)
    def update_config(config_update: AddonConfigUpdate) -> AddonConfigEffective:
        try:
            config_store.update_config(config_update)
            apply_runtime_config()
            return AddonConfigEffective(**config_store.get_effective_config(mask_secrets=True))
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Failed to persist config") from exc

    @router.get("/capabilities", response_model=list[str])
    def get_capabilities() -> list[str]:
        return CAPABILITIES

    return router
