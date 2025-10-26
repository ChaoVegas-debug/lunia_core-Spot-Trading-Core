"""Application entrypoints and helpers."""
from __future__ import annotations

from typing import Any


def create_app(**config: Any):
    """Create a Flask application instance lazily.

    The import occurs inside the function so that environments without Flask
    installed (e.g. offline CI) can still import this module without errors.
    """

    try:
        from flask import Flask
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("Flask is required to create the application") from exc

    app = Flask(__name__)
    for key, value in config.items():
        app.config[key] = value
    return app


def run() -> None:
    """Run the Flask development server if available."""

    app = create_app()
    app.run()
