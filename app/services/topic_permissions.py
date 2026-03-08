from dataclasses import dataclass


RESERVED_NAMESPACE_PREFIXES = (
    "synthia/system/",
    "synthia/core/",
    "synthia/supervisor/",
    "synthia/scheduler/",
    "synthia/policy/",
    "synthia/telemetry/",
)


class TopicPermissionError(ValueError):
    pass


@dataclass(slots=True)
class RealizedPermissions:
    publish: list[str]
    subscribe: list[str]


def realize_topic_permissions(
    addon_id: str,
    publish_topics: list[str],
    subscribe_topics: list[str],
) -> RealizedPermissions:
    normalized_addon_id = addon_id.strip()
    if not normalized_addon_id:
        raise TopicPermissionError("addon_id is required")

    addon_prefix = f"synthia/addons/{normalized_addon_id}/"
    publish = _normalize_topics(publish_topics)
    subscribe = _normalize_topics(subscribe_topics)

    for topic in publish:
        _validate_nonempty_topic(topic)
        _validate_lifecycle_pattern(topic, normalized_addon_id)
        if _is_reserved_topic(topic):
            raise TopicPermissionError(f"Reserved namespace is publish-restricted: {topic}")
        if not topic.startswith(addon_prefix):
            raise TopicPermissionError(
                f"Publish topic must be within addon-owned namespace {addon_prefix}: {topic}"
            )

    for topic in subscribe:
        _validate_nonempty_topic(topic)
        _validate_lifecycle_pattern(topic, normalized_addon_id)
        if not (topic.startswith(addon_prefix) or _is_reserved_topic(topic)):
            raise TopicPermissionError(
                f"Subscribe topic must be addon-owned or reserved namespace topic: {topic}"
            )

    return RealizedPermissions(publish=publish, subscribe=subscribe)


def _normalize_topics(topics: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in topics:
        topic = raw.strip()
        if not topic or topic in seen:
            continue
        seen.add(topic)
        normalized.append(topic)
    return normalized


def _is_reserved_topic(topic: str) -> bool:
    return any(topic.startswith(prefix) for prefix in RESERVED_NAMESPACE_PREFIXES)


def topic_allowed_by_scopes(topic: str, scopes: list[str]) -> bool:
    return any(_mqtt_topic_matches(scope, topic) for scope in scopes)


def validate_publish_topic(topic: str, addon_id: str | None = None) -> str:
    normalized = topic.strip()
    _validate_nonempty_topic(normalized)
    if "+" in normalized or "#" in normalized:
        raise TopicPermissionError(f"Publish topic must not contain MQTT wildcards: {normalized}")
    if _is_reserved_topic(normalized):
        raise TopicPermissionError(f"Reserved namespace is publish-restricted: {normalized}")
    if addon_id and addon_id.strip() and addon_id != "anonymous":
        addon_prefix = f"synthia/addons/{addon_id.strip()}/"
        if not normalized.startswith(addon_prefix):
            raise TopicPermissionError(
                f"Publish topic must be within addon-owned namespace {addon_prefix}: {normalized}"
            )
        _validate_lifecycle_pattern(normalized, addon_id.strip())
    return normalized


def _mqtt_topic_matches(filter_topic: str, topic: str) -> bool:
    filter_levels = filter_topic.split("/")
    topic_levels = topic.split("/")

    for idx, level in enumerate(filter_levels):
        if level == "#":
            return idx == len(filter_levels) - 1
        if idx >= len(topic_levels):
            return False
        if level == "+":
            continue
        if level != topic_levels[idx]:
            return False

    return len(topic_levels) == len(filter_levels)


def _validate_nonempty_topic(topic: str) -> None:
    if not topic:
        raise TopicPermissionError("Topic must not be empty")


def _validate_lifecycle_pattern(topic: str, addon_id: str) -> None:
    addon_prefix = f"synthia/addons/{addon_id}/"
    if not topic.startswith(addon_prefix):
        return
    lifecycle_tail = topic[len(addon_prefix) :]
    if lifecycle_tail in {"announce", "health"}:
        return
    if "/announce" in lifecycle_tail or "/health" in lifecycle_tail:
        raise TopicPermissionError(
            f"Lifecycle topics must be exact and not nested under addon namespace: {topic}"
        )
