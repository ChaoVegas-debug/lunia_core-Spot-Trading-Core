from app.core.arbitrage.engine import ArbitrageConfig, ArbitrageEngine


class StubExchange:
    def __init__(self, price: float) -> None:
        self.price = price

    def get_price(self, symbol: str) -> float:  # noqa: D401
        return self.price

    def place_order(self, *args, **kwargs):  # pragma: no cover - unused
        raise NotImplementedError

    def cancel_order(self, *args, **kwargs):  # pragma: no cover - unused
        raise NotImplementedError

    def get_position(self, symbol):  # pragma: no cover - unused
        return None


def test_arbitrage_engine_detects_spread():
    config = ArbitrageConfig.from_dict(
        {
            "pairs": [{"symbol": "BTCUSDT", "exchanges": ["binance", "okx"]}],
            "spread_threshold_pct": 0.1,
        }
    )
    engine = ArbitrageEngine(
        clients={"binance": StubExchange(100.0), "okx": StubExchange(101.0)},
        config=config,
    )
    opportunities = engine.scan()
    assert len(opportunities) == 1
    opp = opportunities[0]
    assert opp.buy_ex == "binance"
    assert opp.sell_ex == "okx"
    assert opp.spread_pct > 0


def test_arbitrage_engine_below_threshold():
    config = ArbitrageConfig.from_dict(
        {
            "pairs": [{"symbol": "ETHUSDT", "exchanges": ["binance", "okx"]}],
            "spread_threshold_pct": 5.0,
        }
    )
    engine = ArbitrageEngine(
        clients={"binance": StubExchange(100.0), "okx": StubExchange(101.0)},
        config=config,
    )
    assert engine.scan() == []
