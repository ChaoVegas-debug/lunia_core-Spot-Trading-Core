from app.core.ai.supervisor import Supervisor
from app.core.exchange.base import IExchange
from app.core.state import set_state


class DummyClient(IExchange):
    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def get_price(self, symbol: str) -> float:  # pragma: no cover - simple fetch
        return self.price

    def place_order(self, symbol: str, side: str, qty: float, type: str = "MARKET"):
        raise NotImplementedError

    def cancel_order(self, order_id: str):
        raise NotImplementedError

    def get_position(self, symbol: str):
        return None


def test_supervisor_combines_strategies():
    set_state({"spot": {"enabled": True, "weights": {"micro_trend_scalper": 0.5, "scalping_breakout": 0.5}}})
    supervisor = Supervisor(client=DummyClient())
    prices = [100 + i for i in range(30)]
    for price in prices:
        supervisor.update_price("BTCUSDT", price)
    decision = supervisor.get_signals("BTCUSDT")
    assert decision["enable"]["SPOT"] == 1
    assert decision["signals"], "Expected signals from strategies"
    scores = [signal["score"] for signal in decision["signals"]]
    assert scores == sorted(scores, reverse=True)
