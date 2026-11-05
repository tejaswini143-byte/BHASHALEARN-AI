"""Password hashing and JWT access-token helpers."""
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, status

from backend.app.config import get_settings

hasher = PasswordHasher()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def get_jwt_secret() -> str:
    secret = get_settings().jwt_secret_key
    if len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT secret is not configured (set BHASHALEARN_JWT_SECRET_KEY to at least 32 characters)",
        )
    return secret


def create_access_token(student_id: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": student_id,
        "iat": now,
        "exp": now + timedelta(minutes=get_settings().access_token_expire_minutes),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[ALGORITHM], options={"require": ["sub", "exp", "iat"]})
        if payload.get("type") != "access" or not isinstance(payload.get("sub"), str) or not payload["sub"]:
            raise jwt.InvalidTokenError("Invalid token type or subject")
        return payload["sub"]
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
