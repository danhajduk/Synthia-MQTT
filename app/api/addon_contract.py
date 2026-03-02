import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException

from app.models.addon_models import (
    AddonConfigEffective,
    AddonConfigUpdate,
    AddonHealth,
    AddonMeta,
    AddonVersion,
)
from app.services.config_store import ConfigStore
from app.services.health import HealthService

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "manifest.json"
SSAP_API_VERSION = "1.0"


def _load_manifest_metadata() -> dict[str, str]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    return {
        "addon_id": str(manifest["id"]),
        "name": str(manifest.get("name", "Synthia MQTT")),
        "version": str(manifest["version"]),
        "description": str(manifest.get("description", "Distributed MQTT and HA discovery service")),
    }


MANIFEST_METADATA = _load_manifest_metadata()
ADDON_VERSION = AddonVersion(
    addon_id=MANIFEST_METADATA["addon_id"],
    version=MANIFEST_METADATA["version"],
    api_version=SSAP_API_VERSION,
    manifest_version=MANIFEST_METADATA["version"],
)

META = AddonMeta(
    id=MANIFEST_METADATA["addon_id"],
    name=MANIFEST_METADATA["name"],
    version=MANIFEST_METADATA["version"],
    description=MANIFEST_METADATA["description"],
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

    @router.get("/version", response_model=AddonVersion)
    def get_version() -> AddonVersion:
        return ADDON_VERSION

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
