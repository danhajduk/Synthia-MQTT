from pydantic import BaseModel


class AddonUsageSummary(BaseModel):
    addon_id: str
    publish_success: int
    publish_denied: int
    publish_error: int


class BrokerModeSummary(BaseModel):
    mode: str
    direct_access_model: str
    direct_mqtt_supported: bool


class MqttUsageMetricsResponse(BaseModel):
    ok: bool
    publish_count: int
    denied_publish_count: int
    reconnect_count: int
    active_registrations: int
    per_addon_usage: list[AddonUsageSummary]
    broker_mode_summary: BrokerModeSummary
