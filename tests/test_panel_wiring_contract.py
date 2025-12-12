import os
import re
import sys
from pathlib import Path

import pytest
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE_DIR = ROOT / "lunia_core"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

TEST_DB = ROOT / "test_panel_wiring.sqlite"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ.setdefault("DATABASE_URL", f"sqlite:///{TEST_DB}")
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("ADMIN_PASSWORD", "adminpass")
os.environ.setdefault("AUTH_SECRET", "test-secret")
os.environ.setdefault("AUTH_TOKEN_TTL_SECONDS", "3600")
os.environ.setdefault("AUTH_REQUIRED_FOR_TELEMETRY", "1")
os.environ.setdefault("DEFAULT_TENANT_SLUG", "tenant-alpha")
os.environ.setdefault("BRAND_NAME", "Lunia Test")

try:
    from lunia_core.app.services.api import flask_app  # noqa: E402
except ImportError as exc:  # pragma: no cover - dependency guard
    pytest.skip(f"Backend dependencies missing: {exc}", allow_module_level=True)


FRONTEND_ENDPOINTS = ROOT / "frontend/src/api/endpoints.ts"
API_CONTRACT = ROOT / "docs/API_CONTRACT.md"


def _normalize(path: str) -> str:
    path = re.sub(r"\$\{[^}]+\}", ":param", path)
    path = re.sub(r"<[^>]+>", ":param", path)
    path = re.sub(r"\{[^}]+\}", ":param", path)
    return path.rstrip("/") or "/"


def frontend_paths():
    text = FRONTEND_ENDPOINTS.read_text()
    pattern = r"apiFetch(?:<[^>]*>)?\(\s*['\"`](/[^'\"`]+)['\"`]"
    paths = set(re.findall(pattern, text))
    return {_normalize(p) for p in paths}


def backend_paths():
    app = flask_app.app
    collected = set()
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/static"):
            continue
        collected.add(_normalize(rule.rule))
    return collected


def contract_paths():
    body = API_CONTRACT.read_text()
    matches = re.findall(r"(GET|POST|PUT|DELETE) (/[A-Za-z0-9_./{}-]+)", body)
    paths = {_normalize(m[1]) for m in matches}
    return paths


def test_frontend_endpoints_exist_in_backend_and_contract():
    fe = frontend_paths()
    be = backend_paths()
    contract = contract_paths()

    missing_backend = sorted(p for p in fe if p not in be)
    missing_contract = sorted(p for p in fe if p not in contract)

    assert not missing_backend, f"Frontend endpoints missing in backend: {missing_backend}"
    assert not missing_contract, f"Frontend endpoints missing in API contract: {missing_contract}"


