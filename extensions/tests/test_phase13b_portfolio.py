"""
PHASE 13B — VIRTUAL PORTFOLIO: Tests

Comprehensive test suite for portfolio accounting.

All tests use mocks and Decimal precision (no floats, no network, no wall-clock).
"""

import pytest
import json
import ast
from pathlib import Path
from decimal import Decimal
from unittest.mock import MagicMock

from extensions.virtual_portfolio import models, manager, risk_monitor
from extensions.shadow_mode.models import VirtualOrderSpec, ShadowStepResult, StrategyIntent


# ────────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────────────────────

def create_executed_step(symbol, side, fill_price, qty=None, ts_ms=None):
    """Create executed ShadowStepResult."""
    # Build intent with metadata
    intent = StrategyIntent(
        signal="ENTRY_BUY" if side == "BUY" else "ENTRY_SELL",
        confidence=0.85,
        metadata={"quantity": qty} if qty else {}
    )
    
    # Build virtual order
    virtual_order = VirtualOrderSpec(
        symbol=symbol,
        side=side,
        action="ENTRY",
        fill_price=fill_price,
        price_type="IMMEDIATE_FILL"
    )
    
    return ShadowStepResult(
        timestamp_ms=ts_ms or 1737900000000,
        symbol=symbol,
        status="EXECUTED",
        snapshot_health={"is_fresh": True},
        intent=intent,
        virtual_order=virtual_order
    )


def create_snapshot(symbol, trade_price=None, mid=None, best_bid=None, best_ask=None, ts_ms=None):
    """Create market snapshot."""
    return {
        "symbol": symbol,
        "event_ts_ms": ts_ms or 1737900000000,
        "server_ts_ms": ts_ms or 1737900000000,
        "top": {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,
        },
        "trade": {
            "price": trade_price,
        },
        "health": {"is_fresh": True}
    }


# ────────────────────────────────────────────────────────────────────────────────
# T1: LONG PNL (UNREALIZED + REALIZED) USING DECIMAL
# ────────────────────────────────────────────────────────────────────────────────

def test_long_pnl_decimal():
    """Test LONG PnL with Decimal precision."""
    pm = manager.PortfolioManager(starting_equity="10000")
    symbol = "BTCUSDT"
    
    # Entry: BUY 2 @ 50000
    step1 = create_executed_step(symbol, "BUY", "50000", qty="2", ts_ms=1000)
    result1 = pm.on_shadow_step(step1)
    
    assert result1["ok"] is True
    assert result1["audit_record"] is not None
    
    # Check position
    position = pm.positions[symbol]
    assert position.side == "LONG"
    assert position.qty == Decimal("2")
    assert position.avg_entry_price == Decimal("50000")
    
    # Mark to market: price up to 51000
    snap1 = create_snapshot(symbol, trade_price="51000", ts_ms=2000)
    result2 = pm.on_tick(snap1)
    
    assert result2["ok"] is True
    
    # Unrealized PnL = (51000 - 50000) * 2 = 2000
    position = pm.positions[symbol]
    assert position.unrealized_pnl == Decimal("2000")
    assert pm.unrealized_pnl_total == Decimal("2000")
    assert pm.equity == Decimal("10000") + Decimal("2000")  # 12000
    
    # Partial exit: SELL 1 @ 51500
    step2 = create_executed_step(symbol, "SELL", "51500", qty="1", ts_ms=3000)
    result3 = pm.on_shadow_step(step2)
    
    assert result3["ok"] is True
    
    # Realized PnL on reduce: (51500 - 50000) * 1 = 1500
    position = pm.positions[symbol]
    assert position.realized_pnl == Decimal("1500")
    assert position.qty == Decimal("1")  # Reduced to 1
    assert position.avg_entry_price == Decimal("50000")  # Unchanged (WAP on same side)
    
    # Unrealized on remaining: (51500 - 50000) * 1 = 1500 (mark updated to fill_price)
    assert position.unrealized_pnl == Decimal("1500")
    
    # Total PnL
    assert pm.realized_pnl_total == Decimal("1500")
    assert pm.unrealized_pnl_total == Decimal("1500")
    assert pm.equity == Decimal("10000") + Decimal("1500") + Decimal("1500")  # 13000


# ────────────────────────────────────────────────────────────────────────────────
# T2: SHORT PNL (UNREALIZED)
# ────────────────────────────────────────────────────────────────────────────────

def test_short_pnl_unrealized():
    """Test SHORT unrealized PnL."""
    pm = manager.PortfolioManager(starting_equity="10000")
    symbol = "ETHUSDT"
    
    # Entry: SELL 3 @ 3000 (open SHORT)
    step1 = create_executed_step(symbol, "SELL", "3000", qty="3", ts_ms=1000)
    result1 = pm.on_shadow_step(step1)
    
    assert result1["ok"] is True
    
    # Check position
    position = pm.positions[symbol]
    assert position.side == "SHORT"
    assert position.qty == Decimal("3")
    assert position.avg_entry_price == Decimal("3000")
    
    # Mark to market: price down to 2900 (profit for SHORT)
    snap1 = create_snapshot(symbol, trade_price="2900", ts_ms=2000)
    result2 = pm.on_tick(snap1)
    
    assert result2["ok"] is True
    
    # Unrealized PnL = (3000 - 2900) * 3 = 300
    position = pm.positions[symbol]
    assert position.unrealized_pnl == Decimal("300")
    assert pm.equity == Decimal("10000") + Decimal("300")  # 10300
    
    # Mark to market: price up to 3100 (loss for SHORT)
    snap2 = create_snapshot(symbol, trade_price="3100", ts_ms=3000)
    result3 = pm.on_tick(snap2)
    
    assert result3["ok"] is True
    
    # Unrealized PnL = (3000 - 3100) * 3 = -300
    position = pm.positions[symbol]
    assert position.unrealized_pnl == Decimal("-300")
    assert pm.equity == Decimal("10000") - Decimal("300")  # 9700


# ────────────────────────────────────────────────────────────────────────────────
# T3: WAP AVG ENTRY CORRECTNESS
# ────────────────────────────────────────────────────────────────────────────────

def test_wap_avg_entry():
    """Test WAP average entry price calculation."""
    pm = manager.PortfolioManager(starting_equity="10000")
    symbol = "BTCUSDT"
    
    # Entry 1: BUY 1 @ 50000
    step1 = create_executed_step(symbol, "BUY", "50000", qty="1", ts_ms=1000)
    pm.on_shadow_step(step1)
    
    position = pm.positions[symbol]
    assert position.avg_entry_price == Decimal("50000")
    
    # Entry 2: BUY 2 @ 51000
    step2 = create_executed_step(symbol, "BUY", "51000", qty="2", ts_ms=2000)
    pm.on_shadow_step(step2)
    
    # WAP = (50000*1 + 51000*2) / (1+2) = 152000 / 3 ≈ 50666.666...
    position = pm.positions[symbol]
    expected_avg = (Decimal("50000") * Decimal("1") + Decimal("51000") * Decimal("2")) / Decimal("3")
    assert position.avg_entry_price == expected_avg
    assert position.qty == Decimal("3")


# ────────────────────────────────────────────────────────────────────────────────
# T4: RISK MONITOR CRITICAL AT 10% LOSS
# ────────────────────────────────────────────────────────────────────────────────

def test_risk_monitor_critical_at_loss():
    """Test risk monitor CRITICAL alert at 10% loss."""
    # Create portfolio with 10% critical threshold
    pm = manager.PortfolioManager(
        starting_equity="10000",
        warn_dd_pct="0.05",
        crit_dd_pct="0.10"
    )
    symbol = "BTCUSDT"
    
    # Entry: BUY 10 @ 1000 (total 10000 exposure)
    step1 = create_executed_step(symbol, "BUY", "1000", qty="10", ts_ms=1000)
    pm.on_shadow_step(step1)
    
    # Mark down to 900 (10% loss)
    # Loss = (900 - 1000) * 10 = -1000
    # Equity = 10000 - 1000 = 9000
    # Drawdown = 10% from peak
    snap1 = create_snapshot(symbol, trade_price="900", ts_ms=2000)
    result = pm.on_tick(snap1)
    
    assert result["ok"] is True
    
    # Check drawdown
    assert pm.drawdown_pct >= Decimal("0.10")
    
    # Check alerts
    state = pm.get_state()
    alerts = pm.risk_monitor.evaluate(state)
    
    # Should have CRITICAL alert
    assert any(alert.level == "CRITICAL" for alert in alerts)
    assert any("DRAWDOWN_CRITICAL" in alert.code for alert in alerts)


# ────────────────────────────────────────────────────────────────────────────────
# T5: FAIL-CLOSED INVALID PRICE STRING → NO MUTATION
# ────────────────────────────────────────────────────────────────────────────────

def test_fail_closed_invalid_price():
    """Test fail-closed on invalid price string."""
    pm = manager.PortfolioManager(starting_equity="10000")
    symbol = "BTCUSDT"
    
    # Entry with invalid price (non-numeric string)
    step = create_executed_step(symbol, "BUY", "invalid_price", qty="1", ts_ms=1000)
    result = pm.on_shadow_step(step)
    
    # Should fail-closed
    assert result["ok"] is False
    assert result["error"] is not None
    assert result["error"]["code"] == models.PortfolioErrorCode.INVALID_PRICE
    
    # No position created
    assert symbol not in pm.positions
    
    # Equity unchanged
    assert pm.equity == Decimal("10000")


# ────────────────────────────────────────────────────────────────────────────────
# T6: BOUNDED HISTORY RING BUFFER
# ────────────────────────────────────────────────────────────────────────────────

def test_bounded_history_ring():
    """Test bounded equity history ring buffer."""
    pm = manager.PortfolioManager(starting_equity="10000", max_history=3)
    symbol = "BTCUSDT"
    
    # Create 5 ticks (exceeds max_history=3)
    for i in range(5):
        snap = create_snapshot(symbol, trade_price=f"{50000 + i}", ts_ms=1000 + i)
        pm.on_tick(snap)
    
    # Get equity curve
    curve = pm.get_equity_curve(limit=10)
    
    # Should only have last 3 (HEAD DROP)
    assert curve["count"] == 3
    assert len(curve["history"]) == 3
    
    # Oldest should be tick 2 (0-indexed: ticks 2, 3, 4 kept)
    assert curve["history"][0]["ts_ms"] == 1002


# ────────────────────────────────────────────────────────────────────────────────
# T7: AST SCAN NO WALL-CLOCK IMPORTS/CALLS
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_phase13b_ast():
    """AST scan: verify no wall-clock usage in Phase 13B modules."""
    # Deterministic repo root resolution
    test_file_path = Path(__file__).resolve()
    repo_root = None
    
    for parent in test_file_path.parents:
        if (parent / "extensions").exists() and (parent / "extensions").is_dir():
            repo_root = parent
            break
    
    if repo_root is None:
        pytest.fail("Could not find repo root")
    
    # Files to scan
    files_to_scan = [
        repo_root / "extensions/virtual_portfolio/models.py",
        repo_root / "extensions/virtual_portfolio/manager.py",
        repo_root / "extensions/virtual_portfolio/risk_monitor.py",
    ]
    
    # Forbidden call patterns
    forbidden_calls = {
        ("time", "time"): "time.time()",
        ("datetime", "now"): "datetime.now()",
        ("time", "perf_counter"): "time.perf_counter()",
    }
    
    violations = []
    
    for file_path in files_to_scan:
        if not file_path.exists():
            pytest.fail(f"Required file not found: {file_path}")
        
        with open(file_path, "r") as f:
            source = f.read()
        
        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as e:
            pytest.fail(f"Syntax error in {file_path}: {e}")
        
        # Wall-clock detector
        class WallClockDetector(ast.NodeVisitor):
            def __init__(self):
                self.violations = []
            
            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        module = node.func.value.id
                        attr = node.func.attr
                        
                        if (module, attr) in forbidden_calls:
                            self.violations.append(
                                {
                                    "line": node.lineno,
                                    "pattern": forbidden_calls[(module, attr)],
                                }
                            )
                
                self.generic_visit(node)
        
        detector = WallClockDetector()
        detector.visit(tree)
        
        if detector.violations:
            for v in detector.violations:
                violations.append(f"{file_path.name}:{v['line']}: {v['pattern']}")
    
    if violations:
        pytest.fail(f"Wall-clock usage detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# BONUS: DETERMINISM PROOF (STABLE JSON SERIALIZATION)
# ────────────────────────────────────────────────────────────────────────────────

def test_deterministic_serialization():
    """Test deterministic state serialization."""
    pm1 = manager.PortfolioManager(starting_equity="10000")
    pm2 = manager.PortfolioManager(starting_equity="10000")
    symbol = "BTCUSDT"
    
    # Apply identical events to both
    step = create_executed_step(symbol, "BUY", "50000", qty="2", ts_ms=1000)
    pm1.on_shadow_step(step)
    pm2.on_shadow_step(step)
    
    snap = create_snapshot(symbol, trade_price="51000", ts_ms=2000)
    pm1.on_tick(snap)
    pm2.on_tick(snap)
    
    # Serialize states
    state1 = pm1.get_state().to_dict()
    state2 = pm2.get_state().to_dict()
    
    json1 = json.dumps(state1, sort_keys=True, separators=(",", ":"))
    json2 = json.dumps(state2, sort_keys=True, separators=(",", ":"))
    
    # Should be byte-for-byte identical
    assert json1 == json2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
