from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .models import Tenant, User
from .security import hash_password


def create_user(
    session: Session,
    *,
    email: str,
    password: str,
    role: str = "USER",
    is_active: bool = True,
    tenant: Tenant | None = None,
) -> User:
    tenant_id = tenant.id if tenant else None
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
        tenant_id=tenant_id if tenant_id is not None else 1,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def ensure_seed_admin(
    session: Session, *, email: Optional[str], password: Optional[str], tenant: Optional[Tenant]
) -> Optional[User]:
    if not email or not password:
        return None
    existing = session.query(User).filter(User.email == email.lower()).one_or_none()
    if existing:
        return existing
    return create_user(session, email=email, password=password, role="ADMIN", tenant=tenant)


def list_users(session: Session) -> list[User]:
    return session.query(User).order_by(User.created_at.desc()).all()


def update_user(session: Session, user: User, *, role: Optional[str] = None, is_active: Optional[bool] = None) -> User:
    if role:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    session.commit()
    session.refresh(user)
    return user


def touch_last_login(session: Session, user: User) -> None:
    user.last_login_at = datetime.utcnow()
    session.commit()
