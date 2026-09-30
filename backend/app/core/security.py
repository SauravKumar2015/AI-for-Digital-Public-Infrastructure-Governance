import ipaddress
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.auth_models import AuthAccount
from app.core.config import get_settings
from app.core.db import get_db


@dataclass(frozen=True)
class Principal:
    subject: str
    role: str = "citizen"


@lru_cache
def _jwks_client(url: str) -> PyJWKClient:
    return PyJWKClient(url, cache_jwk_set=True, lifespan=300)


def current_user(db: Annotated[Session, Depends(get_db)], request: Request,
                 authorization: Annotated[str | None, Header()] = None,
                 x_dev_user: Annotated[str | None, Header()] = None) -> Principal:
    settings = get_settings()
    if settings.auth_mode == "development" and settings.environment == "production":
        raise HTTPException(status_code=500, detail="Development authentication is disabled in production")
    if settings.auth_mode in {"development", "local-jwt"} and authorization and authorization.startswith("Bearer "):
        if not settings.jwt_secret or len(settings.jwt_secret) < 32:
            raise HTTPException(status_code=500, detail="Local JWT authentication is not configured")
        try:
            claims = jwt.decode(
                authorization.removeprefix("Bearer "), settings.jwt_secret,
                algorithms=["HS256"], issuer=settings.jwt_issuer, audience=settings.jwt_audience,
                options={"require": ["sub", "exp", "iat", "jti", "token_use", "role"]},
            )
            if claims.get("token_use") != "access":
                raise jwt.InvalidTokenError("Not an access token")
            account = db.get(AuthAccount, str(claims["sub"])) if db else None
            if account is None or not account.is_active:
                raise jwt.InvalidTokenError("Account is inactive")
            return Principal(account.id, account.role)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid access token") from exc
    if settings.auth_mode == "local-jwt":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthenticated")
    if settings.auth_mode == "development":
        host = request.client.host if request and request.client else ""
        try:
            local_request = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local_request = False
        if not local_request:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Development identity is available only from localhost")
        if not x_dev_user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Send X-Dev-User for local development or configure OIDC bearer tokens")
        subject = x_dev_user
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
