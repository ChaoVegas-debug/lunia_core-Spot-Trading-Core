from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable, Optional

from flask import g, jsonify, request

from .models import User

ROLE_ORDER = ["USER", "FUND", "TRADER", "ADMIN"]


def current_user() -> Optional[User]:
    return getattr(g, "current_user", None)


def _admin_header_valid(ops_token: str | None) -> bool:
    if not ops_token:
        return False
    header = request.headers.get("X-Admin-Token")
    return header == ops_token


def require_role(*roles: str, allow_admin_header: bool = True, ops_token: str | None = None):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user and not user.is_active:
                return jsonify({"error": "inactive user"}), 403
            if user and (user.role in roles or user.role == "ADMIN"):
                return func(*args, **kwargs)
            if allow_admin_header and _admin_header_valid(ops_token):
                return func(*args, **kwargs)
            return jsonify({"error": "forbidden"}), 403

        return wrapper

    return decorator


def require_auth(optional: bool = False):
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = current_user()
            if user:
                return func(*args, **kwargs)
            if optional:
                return func(*args, **kwargs)
            return jsonify({"error": "unauthorized"}), 401

        return wrapper

    return decorator
