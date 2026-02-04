import sys
import os
import pytest
from unittest.mock import MagicMock

# Global patch for Prometheus to avoid binding ports during tests
# Must be done before any app imports
sys.modules["prometheus_client"] = MagicMock()
sys.modules["prometheus_client.exposition"] = MagicMock()

# Global patch for dotenv to prevent overwriting test-specific env vars
# This ensures that when we set os.environ["OPS_API_TOKEN"] in tests, it sticks
sys.modules["app.compat.dotenv"] = MagicMock()

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Ensure critical env vars are set for testing."""
    os.environ["OPS_API_TOKEN"] = "dev-ops-token"
    
    # Inject Admin Token via custom client
    from lunia_core.app.services.api import flask_app
    from lunia_core.app.services.api.flask_app import app
    from flask.testing import FlaskClient
    
    # Force OPS_TOKEN update since it was loaded at import time
    flask_app.OPS_TOKEN = "dev-ops-token"

    class AuthenticatedClient(FlaskClient):
        def open(self, *args, **kwargs):
            headers = kwargs.get("headers", {})
            # Use environ_base logic's intent but via open override
            # Or just inject into headers directly if not present
            if isinstance(headers, dict) and "X-Admin-Token" not in headers:
                 headers["X-Admin-Token"] = "dev-ops-token"
            elif isinstance(headers, list):
                 headers.append(("X-Admin-Token", "dev-ops-token"))
            # If headers came as None/unset, ensure we create it
            if "headers" not in kwargs:
                kwargs["headers"] = {"X-Admin-Token": "dev-ops-token"}
            
            return super().open(*args, **kwargs)

    app.test_client_class = AuthenticatedClient
