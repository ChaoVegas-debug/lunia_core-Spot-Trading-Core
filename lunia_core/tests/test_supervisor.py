from collections import deque

from app.core.ai.supervisor import Supervisor
from app.core.state import set_state


class DummyExchange:
    def __init__(self, prices):
        self.prices = prices
        self.index = 0

    def get_price(self, _symbol: str):
        price = self.prices[self.index]
        self.index = min(self.index + 1, len(self.prices) - 1)
        return price


def test_supervisor_generates_buy_signal():
    set_state({"spot": {"enabled": True}})
    prices = [98, 95, 95, 96, 97, 98]
    exchange = DummyExchange(prices)
    supervisor = Supervisor(client=exchange)
    for price in prices:
        supervisor.update_price("BTCUSDT", price)
    decision = supervisor.get_signals("BTCUSDT")
    assert decision["enable"]["SPOT"] == 1
    assert any(signal["side"] == "BUY" for signal in decision["signals"])


def test_supervisor_generates_sell_signal():
    set_state({"spot": {"enabled": True}})
    prices = [105, 107, 108, 107, 106, 105]
    exchange = DummyExchange(prices)
    supervisor = Supervisor(client=exchange)
    for price in prices:
        supervisor.update_price("BTCUSDT", price)
    decision = supervisor.get_signals("BTCUSDT")
    assert decision["enable"]["SPOT"] == 1
    assert any(signal["side"] == "SELL" for signal in decision["signals"])


def test_supervisor_respects_global_stop(monkeypatch):
    set_state({"global_stop": True})
    supervisor = Supervisor(client=None)
    supervisor.update_price("BTCUSDT", 100)
    decision = supervisor.get_signals("BTCUSDT")
    assert decision["enable"]["SPOT"] == 0
    set_state({"global_stop": False})
