from app.core.risk.rate_limit import RateLimitConfig, RateLimiter


def test_rate_limiter_blocks_after_threshold(monkeypatch):
    config = RateLimitConfig()
    config.enabled = True
    config.max_per_exchange = 1
    config.max_per_symbol = 1
    limiter = RateLimiter(config)

    allowed, reason = limiter.allow("binance", "okx", "BTCUSDT")
    assert allowed
    assert reason == ""
    limiter.record("binance", "okx", "BTCUSDT")

    allowed, reason = limiter.allow("binance", "okx", "BTCUSDT")
    assert not allowed
    assert "rate limit" in reason
