import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pwdlib import PasswordHash
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth_models import AuthAccount, RefreshSession
from app.core.config import get_settings
from app.core.db import get_db
from app.features.auth.schemas import (LoginRequest, LogoutRequest, RefreshRequest,
                                       SignUpRequest, TokenResponse)
from app.features.feedback.models import UserProfile

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("invalid-account-password")
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_DAYS_FALLBACK = 30


def _require_local_auth() -> None:
    settings = get_settings()
    if settings.auth_mode not in {"local-jwt", "development"} or (
        settings.environment == "production" and settings.auth_mode == "development"
    ):
        raise HTTPException(status_code=404, detail="Local account authentication is disabled")


def _secret() -> str:
    value = get_settings().jwt_secret
    if not value or len(value) < 32:
        raise HTTPException(status_code=503, detail="Set APP_JWT_SECRET to a random value of at least 32 characters")
    return value


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _access_token(account: AuthAccount, now: datetime) -> str:
    settings = get_settings()
    expires = now + timedelta(minutes=settings.jwt_access_minutes)
    return jwt.encode({
        "sub": account.id,
        "role": account.role,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": expires,
        "jti": str(uuid.uuid4()),
        "token_use": ACCESS_TOKEN_TYPE,
    }, _secret(), algorithm="HS256")


def _new_refresh_session(account: AuthAccount, family_id: str, now: datetime) -> tuple[str, RefreshSession]:
    days = get_settings().jwt_refresh_days or REFRESH_TOKEN_DAYS_FALLBACK
    raw_token = secrets.token_urlsafe(48)
    expires = now + timedelta(days=days)
    session = RefreshSession(account_id=account.id, family_id=family_id,
                             token_hash=_token_hash(raw_token), expires_at=expires)
    return raw_token, session


def _issue_tokens(db: Session, account: AuthAccount, family_id: str | None = None) -> dict:
    _secret()
    now = datetime.now(timezone.utc)
    refresh_token, session = _new_refresh_session(account, family_id or str(uuid.uuid4()), now)
    db.add(session)
    return TokenResponse(
        access_token=_access_token(account, now),
        expires_in=get_settings().jwt_access_minutes * 60,
        refresh_token=refresh_token,
        refresh_expires_in=get_settings().jwt_refresh_days * 86400,
    ).model_dump()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def signup(payload: SignUpRequest, db: Db):
    _require_local_auth()
    _secret()
    if db.scalar(select(AuthAccount.id).where(AuthAccount.email == payload.email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    account = AuthAccount(email=payload.email, password_hash=password_hash.hash(payload.password), role="citizen")
    try:
        db.add(account)
        db.flush()
        db.add(UserProfile(subject_id=account.id, display_name=payload.display_name))
        result = _issue_tokens(db, account)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    return result


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Db):
    _require_local_auth()
    _secret()
    account = db.scalar(select(AuthAccount).where(AuthAccount.email == payload.email))
    stored_hash = account.password_hash if account else DUMMY_PASSWORD_HASH
    valid_password = password_hash.verify(payload.password, stored_hash)
    if account is None or not valid_password or not account.is_active:
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    result = _issue_tokens(db, account)
    db.commit()
    return result


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Db):
    _require_local_auth()
    _secret()
    now = datetime.now(timezone.utc)
    old_session = db.scalar(select(RefreshSession).where(
        RefreshSession.token_hash == _token_hash(payload.refresh_token)
    ).with_for_update())
    if old_session is None:
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")
    if old_session.consumed_at is not None or old_session.revoked_at is not None:
        db.execute(update(RefreshSession).where(
            RefreshSession.family_id == old_session.family_id,
            RefreshSession.revoked_at.is_(None),
        ).values(revoked_at=now))
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; sign in again")
    if _utc(old_session.expires_at) <= now:
        old_session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token is invalid or expired")
    account = db.get(AuthAccount, old_session.account_id)
    if account is None or not account.is_active:
        old_session.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Account is unavailable")
    old_session.consumed_at = now
    result = _issue_tokens(db, account, old_session.family_id)
    db.commit()
    return result


@router.post("/logout", status_code=204)
def logout(payload: LogoutRequest, db: Db):
    _require_local_auth()
    session = db.scalar(select(RefreshSession).where(
        RefreshSession.token_hash == _token_hash(payload.refresh_token)
    ))
    if session is not None:
        now = datetime.now(timezone.utc)
        db.execute(update(RefreshSession).where(
            RefreshSession.family_id == session.family_id,
            RefreshSession.revoked_at.is_(None),
        ).values(revoked_at=now))
        db.commit()
