from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.orm import relationship

from .database import Base

JSONType = SQLITE_JSON


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="USER", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)

    audit_events = relationship("AuditEvent", back_populates="actor")


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    updater = relationship("User")


class Limit(Base):
    __tablename__ = "limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(32), nullable=False)  # global|role|user
    subject = Column(String(255), nullable=True)
    key = Column(String(128), nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    updater = relationship("User")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ts = Column(DateTime, default=datetime.utcnow, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(32), nullable=True)
    action = Column(String(128), nullable=False)
    target = Column(String(255), nullable=True)
    result = Column(String(16), nullable=False, default="OK")
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    metadata = Column(JSONType, nullable=True)

    actor = relationship("User", back_populates="audit_events")
