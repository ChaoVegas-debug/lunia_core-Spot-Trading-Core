"""Compatibility shim for the requests library."""
from __future__ import annotations

try:
    import requests as _requests  # type: ignore
except Exception:  # pragma: no cover - offline fallback
    class RequestException(Exception):
        """Fallback requests exception."""

    class _Response:  # pylint: disable=too-few-public-methods
        """Minimal response stub mimicking requests.Response."""

        status_code = 200
        text = ""

        def json(self):  # noqa: D401
            return {}

        def raise_for_status(self) -> None:  # noqa: D401
            if self.status_code >= 400:
                raise RequestException(f"status {self.status_code}")

    class _Session:  # pylint: disable=too-few-public-methods
        """Subset of requests.Session used in tests."""

        def get(self, *args, **kwargs) -> _Response:  # noqa: D401
            return _Response()

        def post(self, *args, **kwargs) -> _Response:  # noqa: D401
            return _Response()

        def delete(self, *args, **kwargs) -> _Response:  # noqa: D401
            return _Response()

    class _RequestsModule:  # pylint: disable=too-few-public-methods
        """Subset of the requests API used by Lunia core."""

        @staticmethod
        def get(*args, **kwargs) -> _Response:  # noqa: D401
            return _Response()

        @staticmethod
        def post(*args, **kwargs) -> _Response:  # noqa: D401
            return _Response()

        RequestException = RequestException
        Response = _Response
        Session = _Session

    requests = _RequestsModule()
else:  # pragma: no cover - production path
    requests = _requests

__all__ = ["requests"]
