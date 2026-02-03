"""
PHASE 13C — HUD API: Tests

Comprehensive test suite for HUD API.

All tests use mocks (no real network, no wall-clock).
"""

import pytest
import json
import ast
from pathlib import Path
from unittest.mock import MagicMock

from extensions.hud_api import models, aggregator


# ────────────────────────────────────────────────────────────────────────────────
# FIXTURES
# ────────────────────────────────────────────────────────────────────────────────

def create_mock_supervisor():
    """Create mock ShadowSupervisor."""
    mock = MagicMock()
    mock.get_status.return_value = {
        "iteration_count": 100,
        "loop_count": 2,
        "loops": {
            "BTCUSDT": {
                "last_audit_ref": "audit_btc_123",
                "error_count": 0,
                "tick_count": 100,
                "executed_count": 25,
                "skipped_stale_count": 50,
                "skipped_noop_count": 25,
                "last_error": None
            },
            "ETHUSDT": {
                "last_audit_ref": "audit_eth_456",
                "error_count": 2,
                "tick_count": 100,
                "executed_count": 20,
                "skipped_stale_count": 55,
                "skipped_noop_count": 23,
                "last_error": {"code": "TEST_ERROR", "message": "Test"}
            }
        }
    }
    return mock


def create_mock_portfolio():
    """Create mock PortfolioManager."""
    mock = MagicMock()
    
    # Mock get_state
    mock_state = MagicMock()
    mock_state.to_dict.return_value = {
        "ts_ms": 1737900000000,
        "equity": "12500.50",
        "starting_equity": "10000",
        "realized_pnl_total": "1500",
        "unrealized_pnl_total": "1000.50",
        "drawdown_abs": "500",
        "drawdown_pct": "0.038",
        "positions": {
            "BTCUSDT": {
                "symbol": "BTCUSDT",
                "side": "LONG",
                "qty": "1.5",
                "avg_entry_price": "50000",
                "mark_price": "51000",
                "unrealized_pnl": "1500",
                "realized_pnl": "0",
                "last_ts_ms": 1737900000000,
                "trade_count": 1
            }
        },
        "alerts": [
            {"ts_ms": 1737900000000, "level": "WARNING", "code": "DRAWDOWN_WARNING", "message": "Drawdown 3.8%"}
        ],
        "last_error": None
    }
    mock.get_state.return_value = mock_state
    
    # Mock get_equity_curve
    mock.get_equity_curve.return_value = {
        "ok": True,
        "history": [
            {"ts_ms": 1737900000000, "equity": "12500.50", "realized_pnl": "1500", "unrealized_pnl": "1000.50"}
        ],
        "count": 1
    }
    
    return mock


def create_mock_pump(symbol, is_fresh=True, has_snapshot=True):
    """Create mock LiveDataPump."""
    mock = MagicMock()
    
    if not has_snapshot:
        mock.get_latest_snapshot.return_value = None
        return mock
    
    mock.get_latest_snapshot.return_value = {
        "ok": True,
        "symbol": symbol,
        "event_ts_ms": 1737900000000,
        "server_ts_ms": 1737900000000,
        "top": {
            "best_bid": "50000.00",
            "best_ask": "50100.00",
            "mid": "50050.00"
        },
        "trade": {
            "price": "50050.00"
        },
        "health": {
            "is_fresh": is_fresh,
            "stale_reason": None if is_fresh else "NO_EVENTS"
        }
    }
    
    return mock


# ────────────────────────────────────────────────────────────────────────────────
# T1: FULL DASHBOARD COMPOSITION
# ────────────────────────────────────────────────────────────────────────────────

def test_full_dashboard_composition():
    """Test complete dashboard state aggregation."""
    # Setup mocks
    supervisor = create_mock_supervisor()
    portfolio = create_mock_portfolio()
    pumps = {
        "BTCUSDT": create_mock_pump("BTCUSDT"),
        "ETHUSDT": create_mock_pump("ETHUSDT")
    }
    
    # Create aggregator
    agg = aggregator.SystemAggregator(
        supervisor=supervisor,
        portfolio=portfolio,
        pumps=pumps
    )
    
    # Get dashboard
    dashboard = agg.get_dashboard()
    
    # Verify structure
    assert "ts_ms" in dashboard
    assert "health" in dashboard
    assert "portfolio" in dashboard
    assert "equity_curve" in dashboard
    assert "market" in dashboard
    assert "loops" in dashboard
    assert "alerts" in dashboard
    assert "stats" in dashboard
    assert "history" in dashboard
    
    # Verify health
    assert dashboard["health"]["supervisor"]["status"] == "UP"
    assert dashboard["health"]["portfolio"]["status"] == "UP"
    assert "BTCUSDT" in dashboard["health"]["pumps"]
    assert "ETHUSDT" in dashboard["health"]["pumps"]
    
    # Verify market
    assert "BTCUSDT" in dashboard["market"]
    assert "ETHUSDT" in dashboard["market"]
    assert dashboard["market"]["BTCUSDT"]["symbol"] == "BTCUSDT"
    assert dashboard["market"]["BTCUSDT"]["best_bid"] == "50000.00"
    
    # Verify loops
    assert "BTCUSDT" in dashboard["loops"]
    assert "ETHUSDT" in dashboard["loops"]
    assert dashboard["loops"]["BTCUSDT"]["last_audit_ref"] == "audit_btc_123"
    
    # Verify stats
    assert dashboard["stats"]["executed"] == 45  # 25 + 20
    assert dashboard["stats"]["skipped_stale"] == 105  # 50 + 55
    
    # Verify portfolio
    assert dashboard["portfolio"] is not None
    assert dashboard["portfolio"]["equity"] == "12500.50"
    
    # Verify alerts
    assert len(dashboard["alerts"]) > 0


# ────────────────────────────────────────────────────────────────────────────────
# T2: FAIL-SAFE PARTIAL DATA
# ────────────────────────────────────────────────────────────────────────────────

def test_fail_safe_partial_data():
    """Test fail-safe when one component fails."""
    # Setup mocks
    supervisor = create_mock_supervisor()
    portfolio = create_mock_portfolio()
    
    # Make one pump raise exception
    pump_btc = create_mock_pump("BTCUSDT")
    pump_eth = MagicMock()
    pump_eth.get_latest_snapshot.side_effect = RuntimeError("Pump crashed!")
    
    pumps = {
        "BTCUSDT": pump_btc,
        "ETHUSDT": pump_eth
    }
    
    # Create aggregator
    agg = aggregator.SystemAggregator(
        supervisor=supervisor,
        portfolio=portfolio,
        pumps=pumps
    )
    
    # Get dashboard (should not crash)
    dashboard = agg.get_dashboard()
    
    # Verify dashboard is valid
    assert dashboard is not None
    assert "health" in dashboard
    
    # Verify BTCUSDT is UP
    assert dashboard["health"]["pumps"]["BTCUSDT"]["status"] == "UP"
    assert dashboard["market"]["BTCUSDT"]["best_bid"] == "50000.00"
    
    # Verify ETHUSDT is DOWN with error
    assert dashboard["health"]["pumps"]["ETHUSDT"]["status"] == "DOWN"
    assert dashboard["health"]["pumps"]["ETHUSDT"]["error"] is not None
    assert "PUMP_ERROR" in dashboard["health"]["pumps"]["ETHUSDT"]["error"]["code"]
    
    # Verify ETHUSDT market mini exists but is empty
    assert "ETHUSDT" in dashboard["market"]
    assert dashboard["market"]["ETHUSDT"]["symbol"] == "ETHUSDT"
    assert dashboard["market"]["ETHUSDT"]["best_bid"] is None


# ────────────────────────────────────────────────────────────────────────────────
# T3: DETERMINISM BYTE-FOR-BYTE
# ────────────────────────────────────────────────────────────────────────────────

def test_determinism_byte_for_byte():
    """Test deterministic JSON output."""
    # Setup mocks (identical)
    supervisor1 = create_mock_supervisor()
    portfolio1 = create_mock_portfolio()
    pumps1 = {
        "BTCUSDT": create_mock_pump("BTCUSDT"),
        "ETHUSDT": create_mock_pump("ETHUSDT")
    }
    
    supervisor2 = create_mock_supervisor()
    portfolio2 = create_mock_portfolio()
    pumps2 = {
        "BTCUSDT": create_mock_pump("BTCUSDT"),
        "ETHUSDT": create_mock_pump("ETHUSDT")
    }
    
    # Create aggregators
    agg1 = aggregator.SystemAggregator(supervisor=supervisor1, portfolio=portfolio1, pumps=pumps1)
    agg2 = aggregator.SystemAggregator(supervisor=supervisor2, portfolio=portfolio2, pumps=pumps2)
    
    # Get dashboards
    dashboard1 = agg1.get_dashboard()
    dashboard2 = agg2.get_dashboard()
    
    # Serialize with stable_json
    json1 = models.stable_json(dashboard1)
    json2 = models.stable_json(dashboard2)
    
    # Should be byte-for-byte identical
    assert json1 == json2


# ────────────────────────────────────────────────────────────────────────────────
# T4: BOUNDED HISTORY RING BUFFER
# ────────────────────────────────────────────────────────────────────────────────

def test_bounded_history_ring():
    """Test bounded history ring buffer."""
    # Setup mocks
    supervisor = create_mock_supervisor()
    portfolio = create_mock_portfolio()
    pumps = {"BTCUSDT": create_mock_pump("BTCUSDT")}
    
    # Create aggregator with max_history=3
    agg = aggregator.SystemAggregator(
        supervisor=supervisor,
        portfolio=portfolio,
        pumps=pumps,
        max_history=3
    )
    
    # Call get_dashboard 5 times
    for i in range(5):
        agg.get_dashboard()
    
    # Get final dashboard
    dashboard = agg.get_dashboard()
    
    # History should only have last 3 entries (HEAD DROP)
    assert len(dashboard["history"]) == 3


# ────────────────────────────────────────────────────────────────────────────────
# T5: NO WALL-CLOCK AST SCAN
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_phase13c_ast():
    """AST scan: verify no wall-clock usage in Phase 13C modules."""
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
        repo_root / "extensions/hud_api/models.py",
        repo_root / "extensions/hud_api/aggregator.py",
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
