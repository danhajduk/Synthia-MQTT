from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.addon_models import OptionalDockerGroup


class InstallStatusResponse(BaseModel):
    mode: Literal["external", "embedded"]
    external_direct_access_mode: Literal["gateway_only", "manual_direct_access"]
    direct_access_summary: str
    setup_state: Literal["unconfigured", "configuring", "ready", "error", "degraded"]
    setup_guidance: str
    configured: bool
    verified: bool
    registered_to_core: bool
    direct_mqtt_supported: bool
    docker_sock_available: bool
    embedded_profile_required: bool
    broker_running: bool
    mqtt_connected: bool
    last_error: str | None
    optional_groups_supported: list[OptionalDockerGroup] = Field(default_factory=list)
    optional_groups_requested: list[str] = Field(default_factory=list)
    optional_groups_active: list[str] = Field(default_factory=list)
    optional_groups_starting: list[str] = Field(default_factory=list)
    optional_groups_failed: list[str] = Field(default_factory=list)
    optional_groups_pending_reconcile: bool = False
    deployment_mode: Literal["base_only", "expanded"] = "base_only"
    optional_groups_reconcile_state: Literal[
        "idle",
        "waiting_for_reconcile",
        "starting",
        "active",
        "failed",
        "mixed",
    ] = "idle"


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
    diagnostic_code: str
    reason: str | None = None


class InstallApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["external", "embedded"]
    external: ExternalConnectionConfig | None = None
    embedded: EmbeddedBrokerConfig | None = None
    base_topic: str | None = None
    ha_discovery_prefix: str | None = None
    external_direct_access_mode: Literal["gateway_only", "manual_direct_access"] = "gateway_only"
    qos_default: int | None = Field(default=None, ge=0, le=2)
    allow_unvalidated: bool = False

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


class InstallModeUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["external", "embedded"]
    external_direct_access_mode: Literal["gateway_only", "manual_direct_access"] = "gateway_only"


class InstallModeUpdateResponse(BaseModel):
    ok: bool
    mode: Literal["external", "embedded"]
    direct_mqtt_supported: bool
    external_direct_access_mode: Literal["gateway_only", "manual_direct_access"]


class OptionalGroupSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_group_ids: list[str] = Field(default_factory=list)


class OptionalGroupSelectionResponse(BaseModel):
    ok: bool
    requested_group_ids: list[str]
    pending_reconcile: bool


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
