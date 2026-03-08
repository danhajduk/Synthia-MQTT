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
        if _is_reserved_topic(topic):
            raise TopicPermissionError(f"Reserved namespace is publish-restricted: {topic}")
        if not topic.startswith(addon_prefix):
            raise TopicPermissionError(
                f"Publish topic must be within addon-owned namespace {addon_prefix}: {topic}"
            )

    for topic in subscribe:
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
