import json
import os
from pathlib import Path
from typing import Any

from app.models.addon_models import AddonConfigUpdate
from app.models.install_models import InstallApplyRequest
from app.services.broker_manager import (
    enable_embedded_broker_stack,
    write_embedded_broker_files,
    write_embedded_compose_override,
)


class ConfigStore:
    def __init__(self, config_path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._base_dir = base_dir
        self._config_path = config_path or base_dir / "runtime" / "config.json"
        self._install_state_path = base_dir / "runtime" / "install_state.json"

    def get_effective_config(self, mask_secrets: bool = False) -> dict[str, Any]:
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
        overrides = self._load_overrides()
        effective = defaults | {
            "mqtt_host": overrides.get("mqtt_host", defaults["mqtt_host"]),
            "mqtt_port": int(overrides.get("mqtt_port", defaults["mqtt_port"])),
            "mqtt_username": overrides.get("mqtt_username", defaults["mqtt_username"]),
            "mqtt_password": overrides.get("mqtt_password", defaults["mqtt_password"]),
            "mqtt_tls": bool(overrides.get("mqtt_tls", defaults["mqtt_tls"])),
            "mqtt_client_id": overrides.get("mqtt_client_id", defaults["mqtt_client_id"]),
            "mqtt_base_topic": overrides.get("mqtt_base_topic", defaults["mqtt_base_topic"]),
            "mqtt_qos": int(overrides.get("mqtt_qos", defaults["mqtt_qos"])),
        }

        if mask_secrets:
            effective["mqtt_password"] = self._mask_secret(effective.get("mqtt_password"))
        return effective

    def update_config(self, config_update: AddonConfigUpdate) -> dict[str, Any]:
        overrides = self._load_overrides()
        update_payload = config_update.model_dump(exclude_none=True)
        overrides.update(update_payload)
        self._save_overrides(overrides)
        return self.get_effective_config()

    def get_install_state(self) -> dict[str, Any]:
        overrides = self._load_overrides()

        mode = overrides.get("mode")
        if mode not in {"external", "embedded"}:
            mode = "external"

        external = overrides.get("external") or {
            "host": overrides.get("mqtt_host", os.getenv("MQTT_HOST", "mosquitto")),
            "port": int(overrides.get("mqtt_port", int(os.getenv("MQTT_PORT", "1883")))),
            "tls": bool(overrides.get("mqtt_tls", self._to_bool(os.getenv("MQTT_TLS", "false")))),
            "username": overrides.get("mqtt_username", os.getenv("MQTT_USERNAME") or None),
            "password": overrides.get("mqtt_password", os.getenv("MQTT_PASSWORD") or None),
        }
        embedded = overrides.get("embedded") or {
            "allow_anonymous": self._to_bool(os.getenv("EMBEDDED_ALLOW_ANONYMOUS", "false")),
            "persistence": self._to_bool(os.getenv("EMBEDDED_PERSISTENCE", "true")),
            "log_type": os.getenv("EMBEDDED_LOG_TYPE", "stdout"),
            "port": int(os.getenv("EMBEDDED_PORT", "1883")),
            "admin_user": os.getenv("EMBEDDED_ADMIN_USER") or external.get("username"),
            "admin_pass": os.getenv("EMBEDDED_ADMIN_PASS") or external.get("password"),
        }
        base_topic = overrides.get("base_topic", overrides.get("mqtt_base_topic", os.getenv("MQTT_BASE_TOPIC", "synthia")))
        ha_discovery_prefix = overrides.get("ha_discovery_prefix", os.getenv("HA_DISCOVERY_PREFIX", "homeassistant"))
        external_direct_access_mode = overrides.get("external_direct_access_mode", "gateway_only")
        if external_direct_access_mode not in {"gateway_only", "manual_direct_access"}:
            external_direct_access_mode = "gateway_only"
        qos_default = int(overrides.get("qos_default", overrides.get("mqtt_qos", int(os.getenv("MQTT_QOS", "1")))))

        external["password"] = self._mask_secret(external.get("password"))
        embedded["admin_pass"] = self._mask_secret(embedded.get("admin_pass"))

        return {
            "mode": mode,
            "external": external,
            "embedded": embedded,
            "base_topic": base_topic,
            "ha_discovery_prefix": ha_discovery_prefix,
            "external_direct_access_mode": external_direct_access_mode,
            "qos_default": qos_default,
        }

    def get_install_session_state(self) -> dict[str, Any]:
        state = self._default_install_session_state()
        raw = self._load_install_session_state()
        if isinstance(raw, dict):
            state["mode"] = raw.get("mode", state["mode"])
            state["setup_state"] = raw.get("setup_state", state["setup_state"])
            state["configured"] = bool(raw.get("configured", state["configured"]))
            state["verified"] = bool(raw.get("verified", state["verified"]))
            state["registered_to_core"] = bool(raw.get("registered_to_core", state["registered_to_core"]))
            state["last_error"] = raw.get("last_error", state["last_error"])
            state["external_test_ok"] = bool(raw.get("external_test_ok", state["external_test_ok"]))
            state["external_test_signature"] = raw.get(
                "external_test_signature",
                state["external_test_signature"],
            )
            state["external_direct_access_mode"] = raw.get(
                "external_direct_access_mode",
                state["external_direct_access_mode"],
            )

        install_config = self.get_install_state()
        mode = install_config.get("mode")
        if mode in {"external", "embedded"}:
            state["mode"] = mode

        return state

    def update_install_session_state(self, **updates: Any) -> dict[str, Any]:
        state = self.get_install_session_state()
        for key in (
            "mode",
            "setup_state",
            "configured",
            "verified",
            "registered_to_core",
            "last_error",
            "external_test_ok",
            "external_test_signature",
            "external_direct_access_mode",
        ):
            if key in updates:
                state[key] = updates[key]
        self._save_install_session_state(state)
        return state

    def set_selected_mode(self, mode: str, external_direct_access_mode: str = "gateway_only") -> dict[str, Any]:
        if mode not in {"external", "embedded"}:
            raise ValueError("Unsupported install mode")
        if external_direct_access_mode not in {"gateway_only", "manual_direct_access"}:
            external_direct_access_mode = "gateway_only"
        overrides = self._load_overrides()
        overrides["mode"] = mode
        overrides["external_direct_access_mode"] = external_direct_access_mode
        self._save_overrides(overrides)
        return self.update_install_session_state(
            mode=mode,
            external_direct_access_mode=external_direct_access_mode,
            setup_state="configuring",
            configured=False,
            verified=False,
            last_error=None,
        )

    def reset_install_session_state(self, mode: str = "external") -> dict[str, Any]:
        state = self._default_install_session_state()
        if mode in {"external", "embedded"}:
            state["mode"] = mode
        self._save_install_session_state(state)
        return state

    def apply_install_config(self, request: InstallApplyRequest) -> dict[str, Any]:
        overrides = self._load_overrides()
        data = request.model_dump(exclude_none=True)
        mode = data["mode"]
        if mode not in {"external", "embedded"}:
            raise ValueError("Unsupported install mode")

        overrides["mode"] = mode
        if "external" in data:
            overrides["external"] = data["external"]
        if "embedded" in data:
            overrides["embedded"] = data["embedded"]
        if "base_topic" in data:
            overrides["base_topic"] = data["base_topic"]
        if "ha_discovery_prefix" in data:
            overrides["ha_discovery_prefix"] = data["ha_discovery_prefix"]
        if "external_direct_access_mode" in data:
            overrides["external_direct_access_mode"] = data["external_direct_access_mode"]
        if "qos_default" in data:
            overrides["qos_default"] = data["qos_default"]

        if mode == "external":
            external = data["external"]
            overrides["mqtt_host"] = external["host"]
            overrides["mqtt_port"] = external["port"]
            overrides["mqtt_tls"] = external["tls"]
            overrides["mqtt_username"] = external.get("username")
            overrides["mqtt_password"] = external.get("password")
        else:
            embedded = data["embedded"]
            overrides["mqtt_host"] = "mosquitto"
            overrides["mqtt_port"] = 1883
            overrides["mqtt_tls"] = False
            overrides["mqtt_username"] = embedded.get("admin_user")
            overrides["mqtt_password"] = embedded.get("admin_pass")

        if "base_topic" in data:
            overrides["mqtt_base_topic"] = data["base_topic"]
        if "qos_default" in data:
            overrides["mqtt_qos"] = data["qos_default"]

        self._save_overrides(overrides)
        self.update_install_session_state(mode=mode, configured=True, last_error=None)
        return self.get_effective_config()

    def apply_embedded_runtime(self, request: InstallApplyRequest) -> tuple[bool, str | None]:
        data = request.model_dump(exclude_none=True)
        if data.get("mode") != "embedded" or "embedded" not in data:
            raise ValueError("embedded config is required when mode is embedded")

        embedded = data["embedded"]
        port = int(embedded["port"])
        broker_dir = self._base_dir / "runtime" / "broker"
        override_file = self._base_dir / "runtime" / "broker" / "docker-compose.override.yml"

        write_embedded_broker_files(broker_dir=broker_dir, embedded_config=embedded)
        write_embedded_compose_override(override_file=override_file, broker_dir=broker_dir, port=port)

        ok, reason = enable_embedded_broker_stack(repo_root=self._base_dir, override_file=override_file)
        return ok, reason

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

    def _load_install_session_state(self) -> dict[str, Any]:
        if not self._install_state_path.exists():
            return {}
        with self._install_state_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return {}
        return data

    def _save_install_session_state(self, state: dict[str, Any]) -> None:
        self._install_state_path.parent.mkdir(parents=True, exist_ok=True)
        with self._install_state_path.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2, sort_keys=True)

    @staticmethod
    def _default_install_session_state() -> dict[str, Any]:
        return {
            "mode": "external",
            "setup_state": "unconfigured",
            "configured": False,
            "verified": False,
            "registered_to_core": False,
            "last_error": None,
            "external_test_ok": False,
            "external_test_signature": None,
            "external_direct_access_mode": "gateway_only",
        }

    @staticmethod
    def _to_bool(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _mask_secret(raw_value: Any) -> str | None:
        if raw_value is None:
            return None

        value = str(raw_value)
        if not value:
            return None
        if len(value) <= 2:
            return "*" * len(value)
        return f"{value[0]}{'*' * (len(value) - 2)}{value[-1]}"
