from app.services.guard.alerts import evaluate_and_alert


def test_alerts_generate_log(monkeypatch, caplog):
    monkeypatch.setenv("ALERTS_ENABLED", "true")
    monkeypatch.setenv("ALERTS_FAIL_THRESHOLD", "1")
    monkeypatch.setenv("ALERTS_NET_ROI_WARN_PCT", "0.9")
    stats = {"pnl": -5.0, "success": 0, "fail": 2, "success_rate": 0.0, "avg_roi": 0.4}
    with caplog.at_level("WARNING"):
        evaluate_and_alert(stats)
    assert "exceed threshold" in caplog.text
    assert "ROI" in caplog.text
