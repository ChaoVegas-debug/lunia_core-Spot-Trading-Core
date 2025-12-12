import os
import sys
from pathlib import Path

import pytest

TEST_DB = Path(__file__).parent / "test_tenant_admin.db"
if TEST_DB.exists():
    TEST_DB.unlink()

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CORE_DIR = ROOT / "lunia_core"
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB}")
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass")
os.environ.setdefault("AUTH_SECRET", "test-secret")
os.environ.setdefault("AUTH_TOKEN_TTL_SECONDS", "3600")
os.environ.setdefault("AUTH_REQUIRED_FOR_TELEMETRY", "1")
os.environ.setdefault("DEFAULT_TENANT_SLUG", "tenant-alpha")
os.environ.setdefault("BRAND_NAME", "Lunia Test")
os.environ.setdefault("BRAND_SUPPORT_EMAIL", "support@example.com")
os.environ.setdefault("BINANCE_USE_TESTNET", "false")
os.environ.setdefault("BINANCE_FUTURES_TESTNET", "false")

try:
    from lunia_core.app.services.api import flask_app  # noqa: E402
    from lunia_core.app.services.auth.database import get_session  # noqa: E402
    from lunia_core.app.services.auth.tenants import ensure_default_tenants  # noqa: E402
    from lunia_core.app.services.auth.users import create_user  # noqa: E402
except ImportError as exc:  # pragma: no cover - dependency guard
    pytest.skip(f"Backend dependencies missing: {exc}", allow_module_level=True)

app = flask_app.app
client = app.test_client()


def _auth_headers(email: str, password: str):
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_can_manage_tenants_and_branding():
    admin_headers = _auth_headers("admin@example.com", "adminpass")

    create = client.post(
        "/admin/tenants",
        headers=admin_headers,
        json={
            "slug": "blue",
            "name": "Blue Corp",
            "domains": ["blue.test"],
            "app_name": "Blue",
            "primary_color": "#00f",
        },
    )
    assert create.status_code == 201
    created = create.get_json()
    tenant_id = created["id"]

    update = client.put(
        f"/admin/tenants/{tenant_id}",
        headers=admin_headers,
        json={"status": "active", "domains": ["blue.test", "blue.example"]},
    )
    assert update.status_code == 200

    branding = client.put(
        f"/admin/tenants/{tenant_id}/branding",
        headers=admin_headers,
        json={"app_name": "Blue Prime", "support_email": "ops@blue.test"},
    )
    assert branding.status_code == 200

    limits = client.put(
        f"/admin/tenants/{tenant_id}/limits",
        headers=admin_headers,
        json={"limits": [{"key": "max_capital", "value": "100000"}]},
    )
    assert limits.status_code == 200

    listing = client.get("/admin/tenants", headers=admin_headers)
    assert listing.status_code == 200
    items = listing.get_json().get("items", [])
    assert any(item["slug"] == "blue" for item in items)

    branding_public = client.get("/branding", headers={"X-Tenant-Id": "blue"})
    assert branding_public.status_code == 200
    assert branding_public.get_json().get("tenant_id") == "blue"
    assert branding_public.get_json().get("brand_name") in {"Blue Prime", "Blue"}

    audit = client.get("/admin/audit", headers=admin_headers)
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.get_json().get("items", [])]
    assert "admin_create_tenant" in actions
    assert "admin_update_tenant_branding" in actions
    assert "admin_update_tenant_limits" in actions


def test_non_admin_cannot_manage_tenants():
    # ensure a non-admin user exists on default tenant
    with get_session() as session:
        default, _ = ensure_default_tenants(session)
        create_user(session, email="viewer@example.com", password="viewpass", role="USER", tenant=default)
    headers = _auth_headers("viewer@example.com", "viewpass")
    resp = client.get("/admin/tenants", headers=headers)
    assert resp.status_code == 403


def test_tenant_resolution_by_header_falls_back_to_default():
    resp = client.get("/branding")
    assert resp.status_code == 200
    assert resp.get_json().get("tenant_id") == os.getenv("DEFAULT_TENANT_SLUG", "tenant-alpha")
