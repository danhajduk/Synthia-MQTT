import json
import hmac
import hashlib
import secrets
from base64 import urlsafe_b64encode
from datetime import datetime, timezone
from pathlib import Path

from app.models.registration_models import (
    DirectMqttCredentials,
    MqttRegistrationRecord,
    MqttRegistrationRequest,
)


class RegistrationStore:
    def __init__(self, path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        self._path = path or (base_dir / "runtime" / "mqtt_registrations.json")
        self._seed_path = base_dir / "runtime" / "mqtt_credential_seed"

    def upsert(self, request: MqttRegistrationRequest) -> MqttRegistrationRecord:
        data = self._load_all()
        addon_id = request.addon_id.strip()
        existing = data.get(addon_id, {})

        direct_credentials: DirectMqttCredentials | None = None
        credential_meta = existing.get("credential_meta") if isinstance(existing, dict) else None
        if request.access_mode in {"direct_mqtt", "both"}:
            direct_credentials, credential_meta = self._issue_direct_credentials(
                addon_id=addon_id,
                reprovision=request.reprovision,
                existing_meta=credential_meta if isinstance(credential_meta, dict) else None,
            )
        else:
            credential_meta = None

        record = MqttRegistrationRecord(
            addon_id=addon_id,
            status="approved",
            access_mode=request.access_mode,
            publish_topics=[topic.strip() for topic in request.publish_topics if topic.strip()],
            subscribe_topics=[topic.strip() for topic in request.subscribe_topics if topic.strip()],
            capabilities=request.capabilities,
            direct_mqtt=direct_credentials,
            updated_at=datetime.now(timezone.utc),
        )
        payload = record.model_dump(mode="json")
        if credential_meta is not None:
            payload["credential_meta"] = credential_meta
        data[record.addon_id] = payload
        self._save_all(data)
        return record

    def _issue_direct_credentials(
        self,
        addon_id: str,
        reprovision: bool,
        existing_meta: dict[str, object] | None,
    ) -> tuple[DirectMqttCredentials, dict[str, object]]:
        seed = self._load_or_create_seed()
        current_version = int(existing_meta.get("version", 1)) if isinstance(existing_meta, dict) else 1
        version = current_version + 1 if reprovision else current_version
        username = f"addon_{addon_id}_mqtt"
        raw = hmac.new(seed, f"{addon_id}:{version}".encode("utf-8"), hashlib.sha256).digest()
        password = urlsafe_b64encode(raw).decode("utf-8").rstrip("=")[:32]
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        meta = {
            "version": version,
            "username": username,
            "password_hash": password_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return DirectMqttCredentials(username=username, password=password), meta

    def _load_or_create_seed(self) -> bytes:
        if self._seed_path.exists():
            return self._seed_path.read_bytes()
        seed = secrets.token_bytes(32)
        self._seed_path.parent.mkdir(parents=True, exist_ok=True)
        self._seed_path.write_bytes(seed)
        return seed

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
