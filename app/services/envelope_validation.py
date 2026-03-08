from typing import Any

from app.services.topic_permissions import RESERVED_NAMESPACE_PREFIXES


class EnvelopeValidationError(ValueError):
    pass


PLATFORM_MESSAGE_TYPES = {
    "announce",
    "health",
    "event",
    "state",
    "command",
    "telemetry",
    "policy",
}


def validate_platform_envelope(topic: str, payload: Any) -> None:
    normalized_topic = topic.strip()
    if not _is_platform_topic(normalized_topic):
        return

    if not isinstance(payload, dict):
        raise EnvelopeValidationError("Platform topic payload must be a JSON object")

    message_type = str(payload.get("type", "")).strip().lower()
    source_addon_id = str(payload.get("source_addon_id", "")).strip()
    timestamp = str(payload.get("timestamp", "")).strip()
    if message_type not in PLATFORM_MESSAGE_TYPES:
        raise EnvelopeValidationError(
            "Platform payload type must be one of: announce, health, event, state, command, telemetry, policy"
        )
    if not source_addon_id:
        raise EnvelopeValidationError("Platform payload requires source_addon_id")
    if not timestamp:
        raise EnvelopeValidationError("Platform payload requires timestamp")
    if "data" not in payload:
        raise EnvelopeValidationError("Platform payload requires data field")


def _is_platform_topic(topic: str) -> bool:
    if topic.startswith("synthia/addons/"):
        return True
    return any(topic.startswith(prefix) for prefix in RESERVED_NAMESPACE_PREFIXES)
