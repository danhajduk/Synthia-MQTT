from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PublishTraceRecord(BaseModel):
    timestamp: datetime
    operation: str
    outcome: Literal["success", "denied", "error"]
    addon_id: str | None = None
    caller_sub: str | None = None
    topic: str | None = None
    detail: str | None = None
    message_id: str | None = None
    correlation_id: str | None = None


class PublishTraceResponse(BaseModel):
    ok: bool
    traces: list[PublishTraceRecord]


class PublishTraceLogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: str = Field(min_length=1)
    outcome: Literal["success", "denied", "error"]
    addon_id: str | None = None
    caller_sub: str | None = None
    topic: str | None = None
    detail: str | None = None
    message_id: str | None = None
    correlation_id: str | None = None
