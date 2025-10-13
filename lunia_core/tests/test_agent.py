import json

from app.core.ai.agent import Agent
from app.core.ai.supervisor import Supervisor
from app.core.exchange.base import IExchange
from app.core.risk.manager import RiskLimits, RiskManager


class DummyExchange(IExchange):
    def __init__(self, price: float, order_status: str = "FILLED"):
        self.price = price
        self.order_status = order_status
        self.orders = []

    def get_price(self, symbol: str) -> float:
        return self.price

    def place_order(self, symbol: str, side: str, qty: float, type: str = "MARKET"):
        order = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "origQty": qty,
            "status": self.order_status,
            "orderId": "mock-1",
        }
        self.orders.append(order)
        return order

    def cancel_order(self, order_id: str):  # pragma: no cover - unused
        return {"orderId": order_id, "status": "CANCELED"}

    def get_position(self, symbol: str):  # pragma: no cover - unused
        return None


def test_agent_success_logs_trade(tmp_path, monkeypatch):
    log_path = tmp_path / "trades.jsonl"
    monkeypatch.setattr("app.core.ai.agent.LOG_PATH", log_path)

    client = DummyExchange(price=100.0)
    supervisor = Supervisor(client=None)
    agent = Agent(client=client, risk=RiskManager(), supervisor=supervisor, subscribe_bus=False)

    result = agent.place_spot_order("BTCUSDT", "BUY", 0.25)
    assert result["ok"] is True

    data = log_path.read_text(encoding="utf-8").strip().splitlines()
    record = json.loads(data[-1])
    assert record["status"] == "FILLED"
    assert record["reason"] == ""
    assert agent.portfolio.realized_pnl >= 0


def test_agent_rejects_trade_when_risk_fails(tmp_path, monkeypatch):
    log_path = tmp_path / "trades.jsonl"
    monkeypatch.setattr("app.core.ai.agent.LOG_PATH", log_path)

    client = DummyExchange(price=100.0)
    limits = RiskLimits(max_symbol_risk_pct=0.1)
    supervisor = Supervisor(client=None)
    agent = Agent(client=client, risk=RiskManager(limits), supervisor=supervisor, subscribe_bus=False)

    result = agent.place_spot_order("BTCUSDT", "BUY", 20.0)
    assert result["ok"] is False
    assert result["reason"] == "max symbol risk exceeded"

    record = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert record["status"] == "REJECTED"


def test_agent_daily_loss_block(monkeypatch, tmp_path):
    log_path = tmp_path / "trades.jsonl"
    monkeypatch.setattr("app.core.ai.agent.LOG_PATH", log_path)

    client = DummyExchange(price=100.0)
    limits = RiskLimits(max_daily_loss_pct=1.0, max_symbol_risk_pct=100.0)
    risk = RiskManager(limits)
    risk.daily_pnl = -20.0  # simulate losses
    supervisor = Supervisor(client=None)
    agent = Agent(client=client, risk=risk, supervisor=supervisor, subscribe_bus=False)

    result = agent.place_spot_order("BTCUSDT", "BUY", 0.25)
    assert not result["ok"]
    assert result["reason"] == "max daily loss exceeded"
