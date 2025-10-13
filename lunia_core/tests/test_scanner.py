from app.services.arbitrage.scanner import ArbitrageFilters, ArbitrageScanner


class DummyExchange:
    def __init__(self, price: float) -> None:
        self.price = price

    def get_price(self, symbol: str) -> float:  # pragma: no cover - simple stub
        return self.price


def test_scanner_computes_roi(tmp_path):
    exchanges = {"binance": DummyExchange(100.0), "okx": DummyExchange(101.0)}
    cfg = tmp_path / "limits.json"
    cfg.write_text(
        """
        {
          "exchanges": {
            "binance": {"taker_fee_pct": 0.1},
            "okx": {"taker_fee_pct": 0.1}
          },
          "symbols": {}
        }
        """,
        encoding="utf-8",
    )
    scanner = ArbitrageScanner(exchanges, ["BTCUSDT"], qty_usd=100.0, limits_path=cfg)
    filters = ArbitrageFilters(min_net_roi_pct=0.0, max_net_roi_pct=100.0, min_net_usd=0.0, top_k=5)
    results = scanner.scan(filters)
    assert results
    opp = results[0]
    assert opp.net_roi_pct != 0
    assert opp.net_profit_usd != 0


def test_scanner_filters_out_low_profit(tmp_path):
    exchanges = {"binance": DummyExchange(100.0), "okx": DummyExchange(100.1)}
    scanner = ArbitrageScanner(exchanges, ["BTCUSDT"], qty_usd=100.0, limits_path=tmp_path / "cfg.json")
    filters = ArbitrageFilters(min_net_roi_pct=5.0, max_net_roi_pct=100.0, min_net_usd=10.0, top_k=5)
    results = scanner.scan(filters)
    assert results == []
