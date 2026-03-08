import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.models.addon_models import (
    AddonConfigEffective,
    AddonConfigUpdate,
    AddonHealth,
    AddonMeta,
    AddonVersion,
)
from app.services.config_store import ConfigStore
from app.services.health import HealthService
from app.services.token_auth import ServiceTokenClaims

MANIFEST_PATH = Path(__file__).resolve().parents[2] / "manifest.json"
SSAP_API_VERSION = "1.0"


def _load_manifest() -> dict[str, object]:
    with MANIFEST_PATH.open("r", encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def _load_manifest_metadata(manifest: dict[str, object]) -> dict[str, str]:
    return {
        "addon_id": str(manifest["id"]),
        "name": str(manifest.get("name", "Synthia MQTT")),
        "version": str(manifest["version"]),
        "description": str(manifest.get("description", "Distributed MQTT and HA discovery service")),
    }


MANIFEST = _load_manifest()
MANIFEST_METADATA = _load_manifest_metadata(MANIFEST)
MANIFEST_PERMISSIONS = [str(permission) for permission in MANIFEST.get("permissions", [])]
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
    "mqtt.ha.discovery.publish",
    "mqtt.ha.state.publish",
]


def build_addon_contract_router(
    config_store: ConfigStore,
    health_service: HealthService,
    apply_runtime_config: Callable[[], None],
    require_config_write_scope: Callable[[], ServiceTokenClaims],
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
    def update_config(
        config_update: AddonConfigUpdate,
        _claims: ServiceTokenClaims = Depends(require_config_write_scope),
    ) -> AddonConfigEffective:
        try:
            config_store.update_config(config_update)
            apply_runtime_config()
            return AddonConfigEffective(**config_store.get_effective_config(mask_secrets=True))
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Failed to persist config") from exc

    @router.get("/capabilities", response_model=list[str])
    def get_capabilities() -> list[str]:
        return CAPABILITIES

    @router.get("/permissions", response_model=list[str])
    def get_permissions() -> list[str]:
        return MANIFEST_PERMISSIONS

    return router
