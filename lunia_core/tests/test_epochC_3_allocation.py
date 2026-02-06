"""
Test Epoch C.3 — Allocation Engine

Tests for deterministic position sizing with confidence and volatility scaling.
"""
import pytest

from lunia_core.app.services.lifecycle.allocation import AllocationEngine
from lunia_core.app.services.lifecycle.models import AllocationPolicy, VolatilityRegime


def test_base_sizing():
    """Base sizing: 1% of equity"""
    policy = AllocationPolicy(base_unit_pct=0.01, min_notional_value=10.0)
    engine = AllocationEngine(policy)
    
    # 100k equity, 1% = $1000, @ $50k/BTC = 0.02 BTC
    qty = engine.calculate_entry_size(
        total_equity=100000.0,
        strategy_confidence=0.5,  # Neutral
        volatility_regime=VolatilityRegime.NORMAL,
        reference_price=50000.0,
    )
    
    assert qty is not None
    assert abs(qty - 0.02) < 0.0001  # 1000 / 50000


def test_high_confidence_larger_size():
    """High confidence → larger position"""
    policy = AllocationPolicy(base_unit_pct=0.01, max_scale_factor=2.5)
    engine = AllocationEngine(policy)
    
    # confidence=0.5 → 1.0x
    qty_neutral = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    # confidence=1.0 → 2.0x (formula: 1.0 + (1.0-0.5)*2.0 = 2.0)
    qty_high = engine.calculate_entry_size(
        100000.0, 1.0, VolatilityRegime.NORMAL, 50000.0
    )
    
    assert qty_high > qty_neutral
    assert abs(qty_high / qty_neutral - 2.0) < 0.01


def test_low_confidence_smaller_size():
    """Low confidence → smaller position"""
    policy = AllocationPolicy(base_unit_pct=0.01)
    engine = AllocationEngine(policy)
    
    qty_neutral = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    qty_low = engine.calculate_entry_size(
        100000.0, 0.0, VolatilityRegime.NORMAL, 50000.0
    )
    
    assert qty_low < qty_neutral
    assert abs(qty_low / qty_neutral - 0.5) < 0.01  # Minimum 50%


def test_high_volatility_smaller_size():
    """High volatility → 50% size reduction"""
    policy = AllocationPolicy(base_unit_pct=0.01, volatility_scalar_enabled=True)
    engine = AllocationEngine(policy)
    
    qty_normal = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    qty_high_vol = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.HIGH, 50000.0
    )
    
    assert abs(qty_high_vol / qty_normal - 0.5) < 0.01


def test_low_volatility_larger_size():
    """Low volatility → 20% size increase"""
    policy = AllocationPolicy(base_unit_pct=0.01, volatility_scalar_enabled=True)
    engine = AllocationEngine(policy)
    
    qty_normal = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    qty_low_vol = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.LOW, 50000.0
    )
    
    assert abs(qty_low_vol / qty_normal - 1.2) < 0.01


def test_below_minimum_returns_none():
    """Position below minimum → None (ABORT)"""
    # Use minimum allowed base_unit (0.001 = 0.1%) which gives $100 on 100k equity
    # But set min_notional to $200 so it fails
    policy = AllocationPolicy(base_unit_pct=0.001, min_notional_value=200.0)
    engine = AllocationEngine(policy)
    
    # 0.1% of 100k = $100, below $200 minimum
    qty = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    assert qty is None


def test_determinism():
    """Same inputs → same output"""
    policy = AllocationPolicy()
    engine = AllocationEngine(policy)
    
    qty1 = engine.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.HIGH, 50000.0
    )
    
    qty2 = engine.calculate_entry_size(
        100000.0, 0.75, VolatilityRegime.HIGH, 50000.0
    )
    
    assert qty1 == qty2


def test_confidence_edge_cases():
    """Test confidence at boundaries"""
    policy = AllocationPolicy(base_unit_pct=0.01, max_scale_factor=2.5)
    engine = AllocationEngine(policy)
    
    # confidence=0.0 → 0.5x (minimum)
    qty_min = engine.calculate_entry_size(
        100000.0, 0.0, VolatilityRegime.NORMAL, 50000.0
    )
    
    # confidence=0.5 → 1.0x
    qty_mid = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    # confidence=1.0 → 2.0x (formula: 1.0 + (1.0-0.5)*2.0 = 2.0)
    qty_max = engine.calculate_entry_size(
        100000.0, 1.0, VolatilityRegime.NORMAL, 50000.0
    )
    
    assert qty_min < qty_mid < qty_max
    assert abs(qty_min / qty_mid - 0.5) < 0.01
    assert abs(qty_max / qty_mid - 2.0) < 0.01


def test_volatility_disabled():
    """Volatility scaling can be disabled"""
    policy = AllocationPolicy(
        base_unit_pct=0.01,
        volatility_scalar_enabled=False
    )
    engine = AllocationEngine(policy)
    
    qty_normal = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.NORMAL, 50000.0
    )
    
    qty_high = engine.calculate_entry_size(
        100000.0, 0.5, VolatilityRegime.HIGH, 50000.0
    )
    
    # Should be same when disabled
    assert qty_normal == qty_high


def test_invalid_inputs():
    """Invalid inputs raise ValueError"""
    policy = AllocationPolicy()
    engine = AllocationEngine(policy)
    
    with pytest.raises(ValueError):
        engine.calculate_entry_size(-100, 0.5, VolatilityRegime.NORMAL, 50000.0)
    
    with pytest.raises(ValueError):
        engine.calculate_entry_size(100000, 1.5, VolatilityRegime.NORMAL, 50000.0)
    
    with pytest.raises(ValueError):
        engine.calculate_entry_size(100000, 0.5, VolatilityRegime.NORMAL, -50000.0)
