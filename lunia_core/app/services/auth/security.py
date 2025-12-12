from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .models import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
AUTH_SECRET = os.getenv("AUTH_SECRET", "change-me")
TOKEN_TTL_SECONDS = int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "86400"))


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user: User) -> Tuple[str, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=TOKEN_TTL_SECONDS)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": expires_at,
    }
    if user.tenant_id:
        payload["tenant_id"] = user.tenant.slug if user.tenant else user.tenant_id
    token = jwt.encode(payload, AUTH_SECRET, algorithm="HS256")
    return token, expires_at


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, AUTH_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user(session: Session, user_id: int) -> Optional[User]:
    return session.query(User).filter(User.id == user_id).one_or_none()


def get_user_by_email(session: Session, email: str, tenant_id: Optional[int] = None) -> Optional[User]:
    query = session.query(User).filter(User.email == email)
    if tenant_id is not None:
        query = query.filter(User.tenant_id == tenant_id)
    return query.one_or_none()
