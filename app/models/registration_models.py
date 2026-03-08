from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MqttRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    addon_id: str = Field(min_length=1)
    access_mode: Literal["gateway_only", "direct_mqtt", "both"]
    publish_topics: list[str] = Field(default_factory=list)
    subscribe_topics: list[str] = Field(default_factory=list)
    capabilities: dict[str, object] = Field(default_factory=dict)
    ha_mode: Literal["none", "gateway_managed", "direct_allowed"] = "none"
    reprovision: bool = False


class DirectMqttCredentials(BaseModel):
    username: str
    password: str


class RegistrationPermissions(BaseModel):
    publish: list[str]
    subscribe: list[str]


class MqttRegistrationRecord(BaseModel):
    addon_id: str
    status: Literal["approved"]
    access_mode: Literal["gateway_only", "direct_mqtt", "both"]
    publish_topics: list[str]
    subscribe_topics: list[str]
    permissions: RegistrationPermissions
    ha_mode: Literal["none", "gateway_managed", "direct_allowed"]
    capabilities: dict[str, object]
    direct_mqtt: DirectMqttCredentials | None = None
    updated_at: datetime


class MqttRegistrationResponse(BaseModel):
    ok: bool
    registration: MqttRegistrationRecord
