from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import settings
from app.schemas.auth import AuthResponse, LoginRequest, LogoutResponse, RegisterRequest, UserProfile

_DB_LOCK = threading.Lock()
_SESSIONS: dict[str, UserProfile] = {}


def _database_path() -> Path:
    prefix = "sqlite:///"
    raw = settings.database_url
    if raw.startswith(prefix):
        db_path = Path(raw[len(prefix) :])
    else:
        db_path = Path("meeting_assistant.db")

    if not db_path.is_absolute():
        db_path = (Path(__file__).resolve().parents[2] / db_path).resolve()

    return db_path


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_database_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db() -> None:
    db_path = _database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _DB_LOCK, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def _public_user(row: sqlite3.Row) -> UserProfile:
    return UserProfile(id=int(row["id"]), username=str(row["username"]), email=str(row["email"]))


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


def register_user(payload: RegisterRequest) -> AuthResponse:
    username = payload.username.strip()
    email = payload.email.strip().lower()

    with _DB_LOCK, _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="用户名或邮箱已存在",
            )

        salt, digest = _hash_password(payload.password)
        cursor = conn.execute(
            """
            INSERT INTO users (username, email, password_salt, password_hash)
            VALUES (?, ?, ?, ?)
            """,
            (username, email, salt, digest),
        )
        conn.commit()

        row = conn.execute(
            "SELECT id, username, email FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="注册失败")

    user = _public_user(row)
    token = _create_session(user)
    return AuthResponse(token=token, user=user)


def login_user(payload: LoginRequest) -> AuthResponse:
    identifier = payload.identifier.strip()

    with _DB_LOCK, _connect() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, password_salt, password_hash
            FROM users
            WHERE username = ? OR email = ?
            """,
            (identifier, identifier.lower()),
        ).fetchone()

    if row is None or not _verify_password(payload.password, row["password_salt"], row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名/邮箱或密码错误",
        )

    user = _public_user(row)
    token = _create_session(user)
    return AuthResponse(token=token, user=user)


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
