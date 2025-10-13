"""Compatibility layer for prometheus_client in offline environments."""
from __future__ import annotations

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Summary, generate_latest, start_http_server
except Exception:  # pragma: no cover - exercised in offline mode
    class _Metric:  # pylint: disable=too-few-public-methods
        """No-op metric placeholder used when prometheus_client is unavailable."""

        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            pass

        def labels(self, *args, **kwargs) -> "_Metric":  # noqa: D401
            return self

        def inc(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def observe(self, *args, **kwargs) -> None:  # noqa: D401
            return None

        def set(self, *args, **kwargs) -> None:  # noqa: D401
            return None

    Counter = Gauge = Histogram = Summary = _Metric  # type: ignore

    class CollectorRegistry:  # pylint: disable=too-few-public-methods
        """No-op collector registry placeholder."""

        def __init__(self, *args, **kwargs) -> None:
            pass

    def generate_latest(*args, **kwargs) -> bytes:  # noqa: D401
        return b""

    def start_http_server(*args, **kwargs) -> None:  # noqa: D401
        return None
else:  # pragma: no cover - real dependency exercised in production
    __all__ = [
        "Counter",
        "Gauge",
        "Histogram",
        "Summary",
        "CollectorRegistry",
        "generate_latest",
        "start_http_server",
    ]
