import pytest

from app.core.capital.allocator import CapitalAllocator


def test_compute_budgets_respects_cap_and_weights():
    allocator = CapitalAllocator(
        max_trade_pct=0.2,
        risk_per_trade_pct=0.01,
        max_symbol_exposure_pct=35,
        max_positions=5,
    )
    result = allocator.compute_budgets(
        equity=10_000,
        cap_pct=0.25,
        reserves={"portfolio": 0.1, "arbitrage": 0.2},
        weights={"a": 0.6, "b": 0.4},
    )
    assert result.tradable_equity == pytest.approx(10_000 * 0.25 * (1 - 0.3))
    assert result.per_strategy["a"] > result.per_strategy["b"]


def test_risk_size_limits_notional():
    allocator = CapitalAllocator(
        max_trade_pct=0.1,
        risk_per_trade_pct=0.02,
        max_symbol_exposure_pct=35,
        max_positions=5,
    )
    size = allocator.risk_size(equity=5_000, stop_pct=0.5)
    assert 0 < size <= 500
