from collections.abc import Callable

from fastapi import Header, HTTPException

from app.services.token_auth import ServiceTokenClaims, ServiceTokenValidator, TokenAuthError


def require_scope(
    validator: ServiceTokenValidator,
    required_scope: str,
) -> Callable[[str | None], ServiceTokenClaims]:
    def _dependency(authorization: str | None = Header(default=None)) -> ServiceTokenClaims:
        try:
            return validator.validate_bearer(
                authorization=authorization,
                required_scope=required_scope,
            )
        except TokenAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    return _dependency
