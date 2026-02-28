import json
import os
from pathlib import Path
from typing import Any

from app.models.addon_models import AddonConfigUpdate


class ConfigStore:
    def __init__(self, config_path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._config_path = config_path or base_dir / "runtime" / "config.json"

    def get_effective_config(self) -> dict[str, Any]:
        defaults = {
            "mqtt_host": os.getenv("MQTT_HOST", "mosquitto"),
            "mqtt_port": int(os.getenv("MQTT_PORT", "1883")),
            "mqtt_username": os.getenv("MQTT_USERNAME") or None,
            "mqtt_password": os.getenv("MQTT_PASSWORD") or None,
            "mqtt_tls": self._to_bool(os.getenv("MQTT_TLS", "false")),
            "mqtt_client_id": os.getenv("MQTT_CLIENT_ID", "synthia-addon-mqtt"),
            "mqtt_base_topic": os.getenv("MQTT_BASE_TOPIC", "synthia"),
            "mqtt_qos": int(os.getenv("MQTT_QOS", "1")),
        }
        return defaults | self._load_overrides()

    def update_config(self, config_update: AddonConfigUpdate) -> dict[str, Any]:
        overrides = self._load_overrides()
        update_payload = config_update.model_dump(exclude_none=True)
        overrides.update(update_payload)
        self._save_overrides(overrides)
        return self.get_effective_config()

    def _load_overrides(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}

        with self._config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return {}

        return data

    def _save_overrides(self, overrides: dict[str, Any]) -> None:
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w", encoding="utf-8") as file:
            json.dump(overrides, file, indent=2, sort_keys=True)

    @staticmethod
    def _to_bool(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
