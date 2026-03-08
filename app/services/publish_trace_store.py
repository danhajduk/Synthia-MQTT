import json
from datetime import datetime, timezone
from pathlib import Path

from app.models.trace_models import PublishTraceLogRequest, PublishTraceRecord


class PublishTraceStore:
    def __init__(self, path: Path | None = None, max_entries: int = 250) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._path = path or (base_dir / "runtime" / "mqtt_publish_traces.json")
        self._max_entries = max(25, max_entries)

    def append(self, request: PublishTraceLogRequest) -> PublishTraceRecord:
        record = PublishTraceRecord(timestamp=datetime.now(timezone.utc), **request.model_dump())
        data = self._load_all()
        data.append(record.model_dump(mode="json"))
        if len(data) > self._max_entries:
            data = data[-self._max_entries :]
        self._save_all(data)
        return record

    def list_recent(self, limit: int = 100) -> list[PublishTraceRecord]:
        bounded_limit = max(1, min(limit, self._max_entries))
        raw = self._load_all()
        records: list[PublishTraceRecord] = []
        for item in reversed(raw):
            if not isinstance(item, dict):
                continue
            try:
                records.append(PublishTraceRecord.model_validate(item))
            except Exception:
                continue
            if len(records) >= bounded_limit:
                break
        return records

    def _load_all(self) -> list[dict[str, object]]:
        if not self._path.exists():
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _save_all(self, payload: list[dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
