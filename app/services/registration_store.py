import json
from datetime import datetime, timezone
from pathlib import Path

from app.models.registration_models import MqttRegistrationRecord, MqttRegistrationRequest


class RegistrationStore:
    def __init__(self, path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._path = path or (base_dir / "runtime" / "mqtt_registrations.json")

    def upsert(self, request: MqttRegistrationRequest) -> MqttRegistrationRecord:
        data = self._load_all()
        record = MqttRegistrationRecord(
            addon_id=request.addon_id.strip(),
            status="approved",
            access_mode=request.access_mode,
            publish_topics=[topic.strip() for topic in request.publish_topics if topic.strip()],
            subscribe_topics=[topic.strip() for topic in request.subscribe_topics if topic.strip()],
            capabilities=request.capabilities,
            updated_at=datetime.now(timezone.utc),
        )
        data[record.addon_id] = record.model_dump(mode="json")
        self._save_all(data)
        return record

    def _load_all(self) -> dict[str, dict[str, object]]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(raw, dict):
            return {}
        cleaned: dict[str, dict[str, object]] = {}
        for key, value in raw.items():
            if isinstance(key, str) and isinstance(value, dict):
                cleaned[key] = value
        return cleaned

    def _save_all(self, payload: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
