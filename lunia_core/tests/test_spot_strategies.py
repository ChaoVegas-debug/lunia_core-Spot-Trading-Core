from app.core.ai.strategies import REGISTRY


def test_bollinger_reversion_signal():
    func = REGISTRY["bollinger_reversion"]
    prices = [100 + (-1) ** i for i in range(39)] + [95]
    ctx = {"sl_pct_default": 0.15, "tp_pct_default": 0.30}
    signals = func("BTCUSDT", prices, ctx)
    assert signals, "Expected bollinger reversion signal"
    assert signals[0].strategy == "bollinger_reversion"


def test_liquidity_snipe_variants():
    func = REGISTRY["liquidity_snipe"]
    prices = [100 + 0.1 * i for i in range(10)]
    ctx = {"sl_pct_default": 0.15, "tp_pct_default": 0.30, "orderbook_depth_ratio": 0.8, "volatility": 0.02}
    signals = func("BTCUSDT", prices, ctx)
    variants = {signal.strategy for signal in signals}
    assert "liquidity_snipe_safe" in variants
    assert "liquidity_snipe_aggressive" in variants
