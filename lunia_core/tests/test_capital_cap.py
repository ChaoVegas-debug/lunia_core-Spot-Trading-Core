from app.core.state import get_state, set_state


def test_capital_cap_runtime_update():
    state = set_state({"ops": {"capital": {"cap_pct": 0.4}}})
    assert get_state()["ops"]["capital"]["cap_pct"] == 0.4
    # Ensure further adjustments clamp within range
    state = set_state({"ops": {"capital": {"cap_pct": 1.5}}})
    assert get_state()["ops"]["capital"]["cap_pct"] == 1.0
