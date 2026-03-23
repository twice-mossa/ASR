from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User
from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile

_SESSIONS: dict[str, UserProfile] = {}
_REVOKED_TOKENS: set[str] = set()


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
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "email": user.email,
        "iat": int(time.time()),
        "exp": int(time.time()) + max(60, settings.jwt_expire_minutes * 60),
        "jti": uuid.uuid4().hex,
        "type": "access",
    }
    token = _encode_jwt(payload)
    return token


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def _encode_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _urlsafe_b64encode(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    payload_b64 = _urlsafe_b64encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_urlsafe_b64encode(signature)}"


def _decode_jwt(token: str) -> dict:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效") from exc

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_signature = hmac.new(settings.jwt_secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_signature = _urlsafe_b64decode(signature_b64)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")

    try:
        payload = json.loads(_urlsafe_b64decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")
    if int(payload.get("exp") or 0) <= int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")
    if str(payload.get("jti") or "") in _REVOKED_TOKENS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效")
    return payload


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

    legacy_user = _SESSIONS.get(token)
    if legacy_user is not None:
        return legacy_user

    payload = _decode_jwt(token)
    return UserProfile(
        id=int(payload["sub"]),
        username=str(payload.get("username") or ""),
        email=str(payload.get("email") or ""),
    )


def logout_user(authorization: str | None) -> LogoutResponse:
    if authorization:
        _, _, token = authorization.partition(" ")
        if token:
            _SESSIONS.pop(token, None)
            try:
                payload = _decode_jwt(token)
            except HTTPException:
                payload = None
            if payload and payload.get("jti"):
                _REVOKED_TOKENS.add(str(payload["jti"]))

    return LogoutResponse(message="已退出登录")
