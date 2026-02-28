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
