import json

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.services.api.flask_app import app


@pytest.mark.requires_flask
def test_ops_capital_endpoints():
    client = app.test_client()
    resp = client.get("/ops/capital")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "cap_pct" in data
    update_resp = client.post(
        "/ops/capital",
        data=json.dumps({"cap_pct": 0.3}),
        content_type="application/json",
    )
    assert update_resp.status_code == 200
    payload = update_resp.get_json()
    assert payload["cap_pct"] == 0.3
