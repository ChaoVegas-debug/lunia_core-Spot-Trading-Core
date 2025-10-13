from app.core.state import reset_state, set_state
from app.services.ai_research.worker import run_research_now


def setup_function(_):
    reset_state()


def teardown_function(_):
    reset_state()


def test_run_research_now_returns_results(monkeypatch):
    set_state({"global_stop": False})
    results = run_research_now(["BTCUSDT", "ETHUSDT"], mode="manual")
    assert len(results) == 2
    assert all("bias" in item for item in results)
