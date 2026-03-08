from typing import Callable

from fastapi import APIRouter, Depends

from app.models.registration_models import (
    MqttRegistrationRequest,
    MqttRegistrationResponse,
)
from app.services.registration_store import RegistrationStore
from app.services.token_auth import ServiceTokenClaims


def build_mqtt_registration_router(
    store: RegistrationStore,
    require_registration_scope: Callable[[], ServiceTokenClaims],
) -> APIRouter:
    router = APIRouter(prefix="/api/mqtt", tags=["mqtt-registration"])

    @router.post("/registrations", response_model=MqttRegistrationResponse)
    def upsert_registration(
        payload: MqttRegistrationRequest,
        _claims: ServiceTokenClaims = Depends(require_registration_scope),
    ) -> MqttRegistrationResponse:
        record = store.upsert(payload)
        return MqttRegistrationResponse(ok=True, registration=record)

    return router
