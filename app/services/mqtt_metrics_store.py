import json
from pathlib import Path


class MqttMetricsStore:
    def __init__(self, path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._path = path or (base_dir / "runtime" / "mqtt_runtime_metrics.json")

    def increment_reconnects(self) -> int:
        state = self._load()
        reconnect_count = int(state.get("reconnect_count", 0)) + 1
        state["reconnect_count"] = reconnect_count
        self._save(state)
        return reconnect_count

    def reconnect_count(self) -> int:
        state = self._load()
        return int(state.get("reconnect_count", 0))

    def _load(self) -> dict[str, int]:
        if not self._path.exists():
            return {"reconnect_count": 0}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {"reconnect_count": 0}
        if not isinstance(raw, dict):
            return {"reconnect_count": 0}
        return {"reconnect_count": int(raw.get("reconnect_count", 0))}

    def _save(self, payload: dict[str, int]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
