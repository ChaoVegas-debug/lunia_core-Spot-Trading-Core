import os
import sys
from pathlib import Path

import pytest

# Configure environment before importing the app
TEST_DB = Path("./test_rbac.sqlite")
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


def test_admin_login_and_me_returns_tenant():
    headers = _auth_headers("admin@example.com", "adminpass")
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.get_json()
    assert body["email"] == "admin@example.com"
    assert body.get("tenant_id") == "tenant-alpha"


def test_admin_can_crud_users_via_api_and_audit_records():
    headers = _auth_headers("admin@example.com", "adminpass")

    create = client.post(
        "/admin/users",
        headers=headers,
        json={"email": "demo@example.com", "password": "demo", "role": "USER"},
    )
    assert create.status_code == 201
    created = create.get_json()
    assert created["email"] == "demo@example.com"
    user_id = created["id"]

    disable = client.put(
        f"/admin/users/{user_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert disable.status_code == 200
    body = disable.get_json()
    assert body["is_active"] is False

    listing = client.get("/admin/users", headers=headers)
    assert listing.status_code == 200
    assert any(item["id"] == user_id and item["is_active"] is False for item in listing.get_json().get("items", []))

    audit = client.get("/admin/audit", headers=headers)
    assert audit.status_code == 200
    actions = [item["action"] for item in audit.get_json().get("items", [])]
    assert "admin_create_user" in actions
    assert "admin_update_user" in actions


def test_admin_can_manage_flags_and_limits_and_audit_records():
    headers = _auth_headers("admin@example.com", "adminpass")

    put_flag = client.put(
        "/admin/flags/FEATURE_TEST",
        headers=headers,
        json={"value": "1"},
    )
    assert put_flag.status_code == 200

    upsert_limit = client.put(
        "/admin/limits",
        headers=headers,
        json={"scope": "global", "key": "max_orders_per_minute", "value": "100"},
    )
    assert upsert_limit.status_code == 200

    audit = client.get("/admin/audit", headers=headers)
    assert audit.status_code == 200
    audit_items = audit.get_json().get("items", [])
    assert any(item["action"] == "admin_update_flag" for item in audit_items)
    assert any(item["action"] == "admin_upsert_limit" for item in audit_items)


def test_user_cannot_access_admin_routes():
    with get_session() as session:
        create_user(session, email="user1@example.com", password="u1pass", role="USER")
    user_headers = _auth_headers("user1@example.com", "u1pass")
    resp = client.get("/admin/users", headers=user_headers)
    assert resp.status_code == 403


def test_telemetry_guard_enforced_and_authorized_path_succeeds():
    unauth = client.get("/ops/state")
    assert unauth.status_code == 401

    admin_headers = _auth_headers("admin@example.com", "adminpass")
    authed = client.get("/ops/state", headers=admin_headers)
    assert authed.status_code == 200
    assert "auto_mode" in authed.get_json()


def test_branding_endpoint_matches_env():
    resp = client.get("/branding")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["brand_name"] == "Lunia Test"
    assert body["tenant_id"] == "tenant-alpha"


def test_activity_logs_and_telemetry_guard_apply():
    headers = _auth_headers("admin@example.com", "adminpass")
    guarded = client.get("/ops/activity")
    assert guarded.status_code == 401

    authed = client.get("/ops/activity", headers=headers)
    assert authed.status_code == 200
    payload = authed.get_json()
    assert "components" in payload

    logs_resp = client.get("/ops/logs", headers=headers)
    assert logs_resp.status_code == 200


def test_ai_signals_and_portfolio_snapshot_shapes():
    headers = _auth_headers("admin@example.com", "adminpass")

    signals = client.get("/ai/signals", headers=headers)
    assert signals.status_code == 200
    assert "items" in signals.get_json()

    snapshot = client.get("/portfolio/snapshot", headers=headers)
    assert snapshot.status_code == 200
    snap_body = snapshot.get_json()
    assert "equity_total_usd" in snap_body
    assert "balances" in snap_body
