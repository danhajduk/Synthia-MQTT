from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InstallStatusResponse(BaseModel):
    mode: Literal["external", "embedded"]
    configured: bool
    verified: bool
    registered_to_core: bool
    docker_sock_available: bool
    embedded_profile_required: bool
    broker_running: bool
    mqtt_connected: bool
    last_error: str | None


class ExternalConnectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    tls: bool = False
    username: str | None = None
    password: str | None = None


class EmbeddedBrokerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow_anonymous: bool = False
    persistence: bool = True
    log_type: str = "stdout"
    port: int = Field(default=1883, ge=1, le=65535)
    admin_user: str | None = None
    admin_pass: str | None = None


class InstallTestExternalResponse(BaseModel):
    ok: bool
    reason: str | None = None


class InstallApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["external", "embedded"]
    external: ExternalConnectionConfig | None = None
    embedded: EmbeddedBrokerConfig | None = None
    base_topic: str | None = None
    ha_discovery_prefix: str | None = None
    qos_default: int | None = Field(default=None, ge=0, le=2)

    @model_validator(mode="after")
    def validate_mode_payload(self) -> "InstallApplyRequest":
        if self.mode == "external" and self.external is None:
            raise ValueError("external config is required when mode is external")
        if self.mode == "embedded" and self.embedded is None:
            raise ValueError("embedded config is required when mode is embedded")
        return self


class InstallApplyResponse(BaseModel):
    ok: bool
    requires_operator_action: bool | None = None
    operator_action: str | None = None
    warnings: list[str] | None = None


class CoreRegistryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(min_length=1)
    core_base_url: str | None = None
    addon_id: str = Field(default="mqtt", min_length=1)
    auth_token: str | None = None


class CoreRegistryResponse(BaseModel):
    ok: bool
    status_code: int | None = None
    reason: str | None = None
