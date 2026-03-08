import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Any


class TokenAuthError(Exception):
    pass


@dataclass(slots=True)
class ServiceTokenClaims:
    sub: str
    aud: str
    jti: str
    scopes: set[str]
    raw: dict[str, Any]


class ServiceTokenValidator:
    def __init__(self, addon_id: str) -> None:
        self._addon_id = addon_id

    def auth_required(self) -> bool:
        return self._to_bool(os.getenv("SYNTHIA_AUTH_REQUIRED", "false"))

    def validate_bearer(self, authorization: str | None, required_scope: str) -> ServiceTokenClaims:
        if not self.auth_required():
            return ServiceTokenClaims(
                sub="anonymous",
                aud=self._expected_audience(),
                jti="auth-disabled",
                scopes={required_scope},
                raw={},
            )

        signing_key = os.getenv("SYNTHIA_JWT_SIGNING_KEY", "")
        if not signing_key:
            raise TokenAuthError("SYNTHIA_JWT_SIGNING_KEY is required when SYNTHIA_AUTH_REQUIRED=true")

        if not authorization or not authorization.startswith("Bearer "):
            raise TokenAuthError("Missing bearer token")
        token = authorization[7:].strip()
        if not token:
            raise TokenAuthError("Missing bearer token")

        parts = token.split(".")
        if len(parts) != 3:
            raise TokenAuthError("Malformed JWT token")

        header_b64, payload_b64, signature_b64 = parts
        header = self._decode_json_segment(header_b64)
        payload = self._decode_json_segment(payload_b64)

        alg = str(header.get("alg", ""))
        if alg != "HS256":
            raise TokenAuthError("Unsupported JWT algorithm")

        self._verify_signature(
            header_b64=header_b64,
            payload_b64=payload_b64,
            signature_b64=signature_b64,
            signing_key=signing_key,
        )

        self._validate_exp(payload)
        self._validate_required_claim(payload, "sub")
        self._validate_required_claim(payload, "aud")
        self._validate_required_claim(payload, "jti")

        expected_aud = self._expected_audience()
        token_aud = str(payload["aud"])
        if token_aud != expected_aud:
            raise TokenAuthError("Invalid token audience")

        scopes = self._extract_scopes(payload)
        if required_scope not in scopes:
            raise TokenAuthError(f"Missing required scope: {required_scope}")

        return ServiceTokenClaims(
            sub=str(payload["sub"]),
            aud=token_aud,
            jti=str(payload["jti"]),
            scopes=scopes,
            raw=payload,
        )

    def _expected_audience(self) -> str:
        return os.getenv("SYNTHIA_TOKEN_AUDIENCE", self._addon_id)

    @staticmethod
    def _validate_required_claim(payload: dict[str, Any], claim_name: str) -> None:
        value = payload.get(claim_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise TokenAuthError(f"Missing required claim: {claim_name}")

    @staticmethod
    def _extract_scopes(payload: dict[str, Any]) -> set[str]:
        raw = payload.get("scp", payload.get("scopes"))
        if raw is None:
            return set()
        if isinstance(raw, str):
            return {part.strip() for part in raw.split() if part.strip()}
        if isinstance(raw, list):
            return {str(item).strip() for item in raw if str(item).strip()}
        return set()

    @staticmethod
    def _validate_exp(payload: dict[str, Any]) -> None:
        exp = payload.get("exp")
        if exp is None:
            raise TokenAuthError("Missing required claim: exp")
        try:
            exp_ts = int(exp)
        except Exception as exc:
            raise TokenAuthError("Invalid exp claim") from exc
        if exp_ts <= int(time.time()):
            raise TokenAuthError("Token expired")

    @staticmethod
    def _decode_json_segment(segment: str) -> dict[str, Any]:
        try:
            raw = ServiceTokenValidator._b64url_decode(segment)
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict):
                raise TokenAuthError("JWT segment is not an object")
            return value
        except TokenAuthError:
            raise
        except Exception as exc:
            raise TokenAuthError("Invalid JWT encoding") from exc

    @staticmethod
    def _verify_signature(
        header_b64: str,
        payload_b64: str,
        signature_b64: str,
        signing_key: str,
    ) -> None:
        message = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(signing_key.encode("utf-8"), message, hashlib.sha256).digest()
        token_sig = ServiceTokenValidator._b64url_decode(signature_b64)
        if not hmac.compare_digest(expected_sig, token_sig):
            raise TokenAuthError("Invalid token signature")

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(value + padding)

    @staticmethod
    def _to_bool(raw_value: str) -> bool:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
