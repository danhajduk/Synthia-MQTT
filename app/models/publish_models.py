from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MqttPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1)
    payload: Any
    retain: bool = True
    qos: int = Field(default=1, ge=0, le=2)


class MqttPublishResponse(BaseModel):
    ok: bool


class MqttGatewayPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    addon_id: str = Field(min_length=1)
    message_type: str = Field(min_length=1)
    payload: dict[str, Any]
    topic: str | None = None
    qos: int | None = Field(default=None, ge=0, le=2)
    retain: bool | None = None


class MqttGatewayPublishResponse(BaseModel):
    ok: bool
    topic: str
    qos: int
    retain: bool


class HaDiscoverySensorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    addon_id: str = Field(min_length=1)
    unique_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    state_topic: str = Field(min_length=1)
    unit_of_measurement: str | None = None
    device_class: str | None = None
    icon: str | None = None


class HaStatePublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    addon_id: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    payload: Any
    retain: bool = True
    qos: int = Field(default=1, ge=0, le=2)
