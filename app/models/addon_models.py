from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OptionalDockerGroup(BaseModel):
    id: str
    name: str
    description: str
    compose_file: str
    depends_on: list[str] = Field(default_factory=list)
    setup_required: bool = False
    default_enabled: bool = False


class AddonMeta(BaseModel):
    id: str
    name: str
    version: str
    description: str
    optional_docker_groups: list[OptionalDockerGroup] = Field(default_factory=list)


class AddonVersion(BaseModel):
    addon_id: str
    version: str
    api_version: str
    manifest_version: str


class AddonHealth(BaseModel):
    status: Literal["healthy", "degraded", "offline", "error", "unconfigured"]
    mqtt_connected: bool
    setup_state: Literal["unconfigured", "configuring", "ready", "error", "degraded"]
    broker_mode: Literal["external", "embedded"]
    broker_reachable: bool
    broker_health: Literal["healthy", "degraded", "unreachable", "unknown"]
    direct_mqtt_supported: bool
    last_error: str | None
    uptime_seconds: int


class AddonConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mqtt_host: str | None = None
    mqtt_port: int | None = None
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_tls: bool | None = None
    mqtt_client_id: str | None = None
    mqtt_base_topic: str | None = None
    mqtt_qos: int | None = None


class AddonConfigEffective(BaseModel):
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_tls: bool
    mqtt_client_id: str
    mqtt_base_topic: str
    mqtt_qos: int
