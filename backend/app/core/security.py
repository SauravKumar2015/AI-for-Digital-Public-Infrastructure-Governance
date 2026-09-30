from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient

from app.core.config import get_settings


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str = "citizen"


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300)


def current_user(authorization: Annotated[str | None, Header()] = None,
                 x_dev_user: Annotated[str | None, Header()] = None) -> Principal:
    settings = get_settings()
    if settings.auth_mode == "development":
        if settings.environment == "production":
            raise HTTPException(status_code=500, detail="Development auth is disabled in production")
        subject = x_dev_user or "local-citizen"
        staff_subjects = {value.strip() for value in settings.development_staff_subjects.split(",") if value.strip()}
        role = "admin" if subject in staff_subjects else "citizen"
        return Principal(subject, role)
    if settings.auth_mode != "oidc" or not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")
    if not (settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url):
        raise HTTPException(status_code=500, detail="OIDC is not fully configured")
    token = authorization.removeprefix("Bearer ")
    try:
        signing_key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, algorithms=["RS256", "ES256"],
                            audience=settings.oidc_audience, issuer=settings.oidc_issuer)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid access token") from exc
    return Principal(str(claims["sub"]), str(claims.get("role", "citizen")))


def require_staff(user: Annotated[Principal, Depends(current_user)]) -> Principal:
    if user.role not in {"analyst", "official", "admin"}:
        raise HTTPException(status_code=403, detail="Staff role required")
    return user
