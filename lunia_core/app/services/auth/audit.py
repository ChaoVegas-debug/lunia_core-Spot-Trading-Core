from __future__ import annotations

from typing import Any, Dict, Optional

from flask import g, request
from sqlalchemy.orm import Session

from .models import AuditEvent, User


def record_audit(
    session: Session,
    *,
    action: str,
    result: str = "OK",
    target: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    actor: Optional[User] = getattr(g, "current_user", None)
    event = AuditEvent(
        actor_user_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        target=target,
        result=result,
        ip=request.headers.get("X-Forwarded-For") or request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        metadata_json=metadata or {},
    )
    session.add(event)
    session.commit()
