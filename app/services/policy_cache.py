import json
import os
import threading
from dataclasses import dataclass
from typing import Any

from app.services.token_auth import ServiceTokenClaims


@dataclass(slots=True)
class GrantRecord:
    grant_id: str | None
    consumer_addon_id: str
    service: str | None
    status: str
    scopes: set[str]


class PolicyCache:
    def __init__(self, service_name: str) -> None:
        self._service_name = service_name
        self._lock = threading.Lock()
        self._grants_by_consumer: dict[str, GrantRecord] = {}
        self._revoked_jti: set[str] = set()
        self._revoked_grant_ids: set[str] = set()
        self._revoked_consumers: set[str] = set()

    def enforcement_enabled(self) -> bool:
        return self._to_bool(os.getenv("SYNTHIA_POLICY_ENFORCEMENT", "false"))

    def ingest(self, topic: str, payload_text: str) -> None:
        if not self.enforcement_enabled():
            return

        data = self._parse_payload(payload_text)
        if data is None:
            return

        if "/policy/grants/" in topic:
            self._apply_grant(data)
            return
        if "/policy/revocations/" in topic:
            self._apply_revocation(data)

    def authorize(self, claims: ServiceTokenClaims, required_scope: str) -> tuple[bool, str | None]:
        if not self.enforcement_enabled():
            return True, None
        if claims.sub == "anonymous":
            return False, "Policy enforcement requires authenticated service token"
        if claims.jti in self._revoked_jti:
            return False, "Token has been revoked"
        if required_scope not in claims.scopes:
            return False, f"Missing required scope: {required_scope}"

        with self._lock:
            if claims.sub in self._revoked_consumers:
                return False, "Consumer addon has been revoked"

            grant = self._grants_by_consumer.get(claims.sub)
            if grant is None:
                return False, f"No active grant for consumer addon: {claims.sub}"
            if grant.status != "active":
                return False, f"Grant is not active (status={grant.status})"
            if grant.grant_id and grant.grant_id in self._revoked_grant_ids:
                return False, "Grant has been revoked"
            if grant.service and grant.service != self._service_name:
                return False, f"Grant service mismatch ({grant.service} != {self._service_name})"
            if grant.scopes and required_scope not in grant.scopes:
                return False, f"Grant missing scope: {required_scope}"

        return True, None

    def _apply_grant(self, data: dict[str, Any]) -> None:
        consumer = str(data.get("consumer_addon_id") or data.get("addon_id") or data.get("sub") or "").strip()
        if not consumer:
            return

        service = str(data.get("service") or "").strip() or None
        if service is not None and service != self._service_name:
            return

        status = str(data.get("status") or "active").strip().lower()
        grant_id_raw = data.get("grant_id")
        grant_id = str(grant_id_raw).strip() if grant_id_raw else None

        record = GrantRecord(
            grant_id=grant_id,
            consumer_addon_id=consumer,
            service=service,
            status=status,
            scopes=self._extract_scopes(data),
        )
        with self._lock:
            if status in {"revoked", "expired"}:
                self._grants_by_consumer.pop(consumer, None)
                if grant_id:
                    self._revoked_grant_ids.add(grant_id)
                return
            self._grants_by_consumer[consumer] = record
            self._revoked_consumers.discard(consumer)
            if grant_id:
                self._revoked_grant_ids.discard(grant_id)

    def _apply_revocation(self, data: dict[str, Any]) -> None:
        jti = str(data.get("jti") or data.get("token_jti") or "").strip()
        grant_id = str(data.get("grant_id") or "").strip()
        consumer = str(data.get("consumer_addon_id") or data.get("addon_id") or "").strip()

        with self._lock:
            if jti:
                self._revoked_jti.add(jti)
            if grant_id:
                self._revoked_grant_ids.add(grant_id)
                for addon_id, grant in list(self._grants_by_consumer.items()):
                    if grant.grant_id == grant_id:
                        self._grants_by_consumer.pop(addon_id, None)
            if consumer:
                self._revoked_consumers.add(consumer)
                self._grants_by_consumer.pop(consumer, None)

    @staticmethod
    def _parse_payload(payload_text: str) -> dict[str, Any] | None:
        try:
            value = json.loads(payload_text)
        except Exception:
            return None
        if not isinstance(value, dict):
            return None
        return value

    @staticmethod
    def _extract_scopes(data: dict[str, Any]) -> set[str]:
        raw = data.get("scp", data.get("scopes"))
        if raw is None:
            return set()
        if isinstance(raw, str):
            return {item.strip() for item in raw.split() if item.strip()}
        if isinstance(raw, list):
            return {str(item).strip() for item in raw if str(item).strip()}
        return set()

    @staticmethod
    def _to_bool(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
