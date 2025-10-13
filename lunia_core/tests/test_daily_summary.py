from types import SimpleNamespace

import pytest

pytest.importorskip("flask", reason="Flask not available in offline/proxy env")

from app.db.reporting import (
    arbitrage_daily_summary,
    record_arbitrage_execution,
    record_arbitrage_proposal,
)
from app.services.telegram.bot import daily_summary_text


class DummyExec:
    def __init__(self, exec_id: str, status: str, pnl: float, fees: float) -> None:
        self.exec_id = exec_id
        self.proposal_id = "prop-" + exec_id
        self.mode = "dry"
        self.status = status
        self.pnl_usd = pnl
        self.fees_usd = fees
        self.started_at = 0.0
        self.completed_at = 0.0
        self.steps = []

    def to_dict(self) -> dict:
        return {
            "exec_id": self.exec_id,
            "proposal_id": self.proposal_id,
            "mode": self.mode,
            "status": self.status,
            "pnl_usd": self.pnl_usd,
            "fees_usd": self.fees_usd,
            "message": "",
            "steps": self.steps,
        }


def test_daily_summary_text(monkeypatch):
    monkeypatch.setenv("ALERTS_ENABLED", "false")
    opportunity = SimpleNamespace(
        proposal_id="prop-1",
        symbol="BTCUSDT",
        buy_exchange="binance",
        sell_exchange="okx",
        qty_usd=100.0,
        gross_spread_pct=0.6,
        fees_total_pct=0.1,
        slippage_est_pct=0.05,
        net_roi_pct=0.45,
        net_profit_usd=0.45,
        meta={},
    )
    record_arbitrage_proposal(opportunity, filtered_out=False, reason=None)
    record_arbitrage_execution(DummyExec("1", "FILLED", 5.0, 0.1), auto_trigger=False)
    record_arbitrage_execution(DummyExec("2", "FAILED", -1.0, 0.05), auto_trigger=False)

    stats = arbitrage_daily_summary()
    assert stats["success"] >= 1
    text = daily_summary_text()
    assert "📊 Daily Arbitrage Summary" in text
    assert "Success:" in text
    assert "Avg ROI" in text
