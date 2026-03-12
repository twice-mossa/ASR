from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import User
from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile

_SESSIONS: dict[str, UserProfile] = {}


def _public_user(user: User) -> UserProfile:
    return UserProfile(id=int(user.id), username=str(user.username), email=str(user.email))


def _hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return (
        base64.b64encode(salt).decode("utf-8"),
        base64.b64encode(digest).decode("utf-8"),
    )


def _verify_password(password: str, salt_b64: str, digest_b64: str) -> bool:
    salt = base64.b64decode(salt_b64.encode("utf-8"))
    _, candidate_b64 = _hash_password(password, salt=salt)
    return hmac.compare_digest(candidate_b64, digest_b64)


def _create_session(user: UserProfile) -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = user
    return token


def _get_session() -> Session:
    return SessionLocal()


def register_user(payload: RegisterRequest) -> AuthResponse:
    username = payload.username.strip()
    email = payload.email.strip().lower()

    with _get_session() as db:
        existing = db.execute(
            select(User).where(or_(User.username == username, User.email == email))
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已存在")

        salt, digest = _hash_password(payload.password)
        user = User(
            username=username,
            email=email,
            password_salt=salt,
            password_hash=digest,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名或邮箱已存在") from None
        db.refresh(user)

    public_user = _public_user(user)
    token = _create_session(public_user)
    return AuthResponse(token=token, user=public_user)


def login_user(payload: LoginRequest) -> AuthResponse:
    identifier = payload.identifier.strip()

    with _get_session() as db:
        user = db.execute(
            select(User).where(or_(User.username == identifier, User.email == identifier.lower()))
        ).scalar_one_or_none()

    if user is None or not _verify_password(payload.password, user.password_salt, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
        )

    public_user = _public_user(user)
    token = _create_session(public_user)
    return AuthResponse(token=token, user=public_user)


def get_current_user(authorization: str | None) -> UserProfile:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少认证信息")

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证格式错误")

    user = _SESSIONS.get(token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

    return user


def logout_user(authorization: str | None) -> LogoutResponse:
    if authorization:
        _, _, token = authorization.partition(" ")
        if token:
            _SESSIONS.pop(token, None)

    return LogoutResponse(message="已退出登录")
