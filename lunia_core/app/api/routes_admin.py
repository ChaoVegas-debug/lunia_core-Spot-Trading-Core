"""Admin API routes (minimal placeholder)."""
from __future__ import annotations

from typing import Any

try:
    from flask import Blueprint, jsonify
except Exception:  # noqa: BLE001
    Blueprint = None  # type: ignore[assignment]
    jsonify = None  # type: ignore[assignment]


def get_blueprint() -> Any:
    """Return a Blueprint if Flask is available, otherwise None."""

    if Blueprint is None:
        return None
    blueprint = Blueprint("admin", __name__, url_prefix="/admin")

    @blueprint.route("/health", methods=["GET"])
    def health() -> Any:  # noqa: D401
        """Report a simple OK status for admin checks."""

        if jsonify is None:
            return {"status": "ok"}
        return jsonify({"status": "ok"})

    return blueprint
