import math

from app.core.state import set_state
from app.services.arbitrage.scanner import ArbitrageFilters, ArbitrageScanner


class _MockExchange:
    def __init__(self, price: float) -> None:
        self._price = price

    def get_price(self, _symbol: str) -> float:
        return self._price


def test_scanner_adaptive_quantity(tmp_path, monkeypatch):
    exchanges = {
        "buy": _MockExchange(100.0),
        "sell": _MockExchange(101.0),
    }
    scanner = ArbitrageScanner(exchanges=exchanges, symbols=["BTCUSDT"], qty_usd=200.0)
    # patch limits to enforce shallow depth
    limits = {
        "exchanges": {
            "buy": {"depth_usd": 80.0, "taker_fee_pct": 0.05},
            "sell": {"depth_usd": 120.0, "taker_fee_pct": 0.05},
        },
        "symbols": {
            "BTCUSDT": {"depth_usd": 80.0, "volatility_pct": 2.0}
        },
        "slippage_factor": 1.0,
        "transfer_eta_sec": {"internal": 5.0, "chain": 300.0},
    }
    scanner._limits = limits  # type: ignore[attr-defined]
    set_state({"arb": {"qty_min_usd": 25.0, "qty_max_usd": 150.0, "qty_usd": 120.0}})
    filters = ArbitrageFilters(top_k=1)
    opportunities = scanner.scan(filters)
    assert opportunities, "Scanner should return opportunity"
    qty = opportunities[0].qty_usd
    # depth cap is 0.25 * min(depth_buy, depth_sell) => 20, volatility reduces further
    assert 25.0 <= qty <= 60.0
    assert math.isclose(opportunities[0].meta["qty"]["base_usd"], 200.0)
