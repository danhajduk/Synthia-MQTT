from typing import Callable

from fastapi import APIRouter, Depends, HTTPException

from app.models.registration_models import (
    MqttRegistrationRequest,
    MqttRegistrationResponse,
)
from app.services.config_store import ConfigStore
from app.services.registration_store import RegistrationStore
from app.services.topic_permissions import TopicPermissionError
from app.services.token_auth import ServiceTokenClaims


def build_mqtt_registration_router(
    store: RegistrationStore,
    config_store: ConfigStore,
    require_registration_scope: Callable[[], ServiceTokenClaims],
) -> APIRouter:
    router = APIRouter(prefix="/api/mqtt", tags=["mqtt-registration"])

    @router.post("/registrations", response_model=MqttRegistrationResponse)
    def upsert_registration(
        payload: MqttRegistrationRequest,
        _claims: ServiceTokenClaims = Depends(require_registration_scope),
    ) -> MqttRegistrationResponse:
        install_state = config_store.get_install_session_state()
        broker_mode = "embedded" if install_state.get("mode") == "embedded" else "external"
        try:
            record = store.upsert(payload, broker_mode=broker_mode)
        except TopicPermissionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return MqttRegistrationResponse(ok=True, registration=record)

    return router
