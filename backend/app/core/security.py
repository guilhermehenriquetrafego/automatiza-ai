"""Security utilities — password hashing, JWT tokens, session encryption."""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from passlib.context import CryptContext
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.models import User, async_session

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_token(user_id: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError, KeyError):
        raise HTTPException(401, "Invalid token")

    async with async_session() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(401, "User not found or inactive")
        return user


# Session encryption for storing OLX browser sessions
from cryptography.fernet import Fernet
_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = settings.SECRET_KEY.encode("utf-8")[:32].ljust(32, b"0")
        _fernet = Fernet(Fernet.generate_key())  # In production, use a stable key
    return _fernet


def encrypt_session(data: str) -> str:
    return _get_fernet().encrypt(data.encode()).decode()


def decrypt_session(encrypted: str) -> dict:
    return _get_fernet().decrypt(encrypted.encode()).decode()
