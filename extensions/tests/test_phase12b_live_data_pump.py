"""
PHASE 12B — LIVE DATA PUMP: Tests

Comprehensive test suite for market data ingestion.

All tests use mocks (no real network).
"""

import pytest
import json
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch
from decimal import Decimal

from extensions.live_data_pump import orderbook, snapshot_factory, pump, models, store


# ────────────────────────────────────────────────────────────────────────────────
# T1: ORDERBOOK CANONICAL SORTING
# ────────────────────────────────────────────────────────────────────────────────

def test_orderbook_canonical_sorting():
    """Test orderbook sorts bids DESC, asks ASC."""
    book = orderbook.LocalOrderBook("BTCUSDT", depth=5)
    
    # Feed unordered levels
    unordered_bids = [
        ["50000.00", "1.5"],
        ["50100.00", "2.0"],
        ["49900.00", "0.8"],
    ]
    
    unordered_asks = [
        ["50200.00", "1.0"],
        ["50150.00", "0.5"],
        ["50300.00", "2.5"],
    ]
    
    book.initialize_from_snapshot(unordered_bids, unordered_asks, 12345)
    
    bids, asks = book.get_sorted_levels()
    
    # Bids should be DESC (highest first)
    assert bids[0][0] == "50100.00"
    assert bids[1][0] == "50000.00"
    assert bids[2][0] == "49900.00"
    
    # Asks should be ASC (lowest first)
    assert asks[0][0] == "50150.00"
    assert asks[1][0] == "50200.00"
    assert asks[2][0] == "50300.00"


# ────────────────────────────────────────────────────────────────────────────────
# T2: GAP DETECTION (UPDATE ID SEQUENCE)
# ────────────────────────────────────────────────────────────────────────────────

def test_gap_detection_update_id_sequence():
    """Test gap detection when update IDs are non-sequential."""
    book = orderbook.LocalOrderBook("BTCUSDT")
    
    # Initialize with update ID 1000
    book.initialize_from_snapshot(
        [["50000.00", "1.0"]],
        [["50100.00", "1.0"]],
        1000
    )
    
    assert book.is_synced is True
    assert book.last_update_id == 1000
    
    # Apply update with ID 1001 (sequential, OK)
    applied = book.apply_update(
        [["50001.00", "1.5"]],
        [["50101.00", "1.5"]],
        1001
    )
    assert applied is True
    assert book.is_synced is True
    
    # Apply update with ID 1005 (gap detected, should fail)
    applied = book.apply_update(
        [["50002.00", "1.0"]],
        [["50102.00", "1.0"]],
        1005  # Gap: 1001 → 1005 (missing 1002, 1003, 1004)
    )
    assert applied is False
    assert book.is_synced is False


# ────────────────────────────────────────────────────────────────────────────────
# T3: SNAPSHOT ATOMICITY (IMMUTABILITY)
# ────────────────────────────────────────────────────────────────────────────────

def test_snapshot_atomicity_immutability():
    """Test snapshot is immutable copy (book mutations don't affect it)."""
    book = orderbook.LocalOrderBook("BTCUSDT", depth=10)
    
    # Initialize book
    book.initialize_from_snapshot(
        [["50000.00", "1.0"]],
        [["50100.00", "1.0"]],
        100
    )
    
    # Create snapshot
    snapshot = snapshot_factory.create_market_snapshot(book, is_fresh=True)
    
    # Verify snapshot has data
    assert len(snapshot["book"]["bids"]) == 1
    assert snapshot["book"]["bids"][0][0] == "50000.00"
    
    # Mutate book
    book.apply_update(
        [["50000.00", "0"], ["49999.00", "2.0"]],  # Remove old bid, add new
        [],
        101
    )
    
    # Original snapshot should NOT change
    assert len(snapshot["book"]["bids"]) == 1
    assert snapshot["book"]["bids"][0][0] == "50000.00"
    
    # New snapshot should reflect changes
    snapshot2 = snapshot_factory.create_market_snapshot(book, is_fresh=True)
    assert snapshot2["book"]["bids"][0][0] == "49999.00"


# ────────────────────────────────────────────────────────────────────────────────
# T4: SNAPSHOT STABILITY (DETERMINISTIC OUTPUT)
# ────────────────────────────────────────────────────────────────────────────────

def test_snapshot_stability_deterministic_output():
    """Test same inputs produce identical snapshot."""
    book = orderbook.LocalOrderBook("BTCUSDT", depth=5)
    
    # Initialize with fixed data
    book.initialize_from_snapshot(
        [["50000.00", "1.0"], ["49999.00", "2.0"]],
        [["50100.00", "1.5"], ["50101.00", "0.8"]],
        200
    )
    
    # Create two snapshots with identical inputs
    snapshot1 = snapshot_factory.create_market_snapshot(
        book,
        ticker_price="50050.00",
        event_ts_ms=1737900000000,
        is_fresh=True
    )
    
    snapshot2 = snapshot_factory.create_market_snapshot(
        book,
        ticker_price="50050.00",
        event_ts_ms=1737900000000,
        is_fresh=True
    )
    
    # Serialize to canonical JSON
    json1 = json.dumps(snapshot1, sort_keys=True, separators=(',', ':'))
    json2 = json.dumps(snapshot2, sort_keys=True, separators=(',', ':'))
    
    # Should be byte-for-byte identical
    assert json1 == json2


# ────────────────────────────────────────────────────────────────────────────────
# T5: QUEUE BACKPRESSURE BOUNDEDNESS (RING BUFFER)
# ────────────────────────────────────────────────────────────────────────────────

def test_queue_backpressure_boundedness():
    """Test snapshot store ring buffer is bounded (HEAD DROP)."""
    # Create store with small capacity
    snapshot_store = store.SnapshotStore("BTCUSDT", max_snapshots=3)
    
    # Add 5 snapshots (exceeds capacity)
    for i in range(5):
        snapshot_store.add_snapshot({
            "id": i,
            "event_ts_ms": 1000 + i,
        })
    
    # Should only have last 3 (HEAD DROP - oldest evicted)
    recent = snapshot_store.get_recent_snapshots(limit=10)
    
    assert len(recent) == 3
    assert recent[0]["id"] == 2  # Oldest kept
    assert recent[1]["id"] == 3
    assert recent[2]["id"] == 4  # Newest


# ────────────────────────────────────────────────────────────────────────────────
# T6: REST POLLING WITH MOCKS (NO REAL NETWORK)
# ────────────────────────────────────────────────────────────────────────────────

def test_rest_polling_with_mocks():
    """Test pump polling cycle with mocked responses."""
    from extensions.exchange_connectivity.binance_client import BinanceClient
    
    # Create mock client
    mock_client = MagicMock(spec=BinanceClient)
    
    # Mock depth response
    mock_client.depth.return_value = {
        "ok": True,
        "data": {
            "bids": [["50000.00", "1.0"], ["49999.00", "2.0"]],
            "asks": [["50100.00", "1.5"], ["50101.00", "0.8"]],
            "lastUpdateId": 1000
        }
    }
    
    # Mock ticker response
    mock_client.ticker_price.return_value = {
        "ok": True,
        "data": {"symbol": "BTCUSDT", "price": "50050.00"}
    }
    
    # Mock server time
    mock_client.server_time.return_value = {
        "ok": True,
        "data": {"serverTime": 1737900000000}
    }
    
    # Create pump
    data_pump = pump.LiveDataPump(mock_client, "BTCUSDT", depth=10)
    
    # Initialize
    init_result = data_pump.initialize()
    assert init_result["ok"] is True
    
    # Tick once
    tick_result = data_pump.tick()
    assert tick_result["ok"] is True
    assert tick_result["depth_ok"] is True
    assert tick_result["ticker_ok"] is True
    
    # Get snapshot
    snapshot = data_pump.get_latest_snapshot()
    assert snapshot is not None
    assert snapshot["ok"] is True
    assert snapshot["symbol"] == "BTCUSDT"
    assert len(snapshot["book"]["bids"]) == 2
    assert snapshot["trade"]["price"] == "50050.00"


# ────────────────────────────────────────────────────────────────────────────────
# T7: NO WALL-CLOCK IMPORTS (AST SCAN)
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_phase12b_ast():
    """AST scan: verify no wall-clock usage in Phase 12B modules."""
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
        repo_root / "extensions/live_data_pump/orderbook.py",
        repo_root / "extensions/live_data_pump/snapshot_factory.py",
        repo_root / "extensions/live_data_pump/pump.py",
        repo_root / "extensions/live_data_pump/models.py",
        repo_root / "extensions/live_data_pump/store.py",
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
        
        with open(file_path, 'r') as f:
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
                            self.violations.append({
                                "line": node.lineno,
                                "pattern": forbidden_calls[(module, attr)],
                            })
                
                self.generic_visit(node)
        
        detector = WallClockDetector()
        detector.visit(tree)
        
        if detector.violations:
            for v in detector.violations:
                violations.append(f"{file_path.name}:{v['line']}: {v['pattern']}")
    
    if violations:
        pytest.fail(f"Wall-clock usage detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# T8: NO TRADING ENDPOINTS STATIC SCAN
# ────────────────────────────────────────────────────────────────────────────────

def test_no_trade_endpoints_present_static_scan():
    """Static scan for forbidden endpoint patterns."""
    test_file_path = Path(__file__).resolve()
    repo_root = None
    
    for parent in test_file_path.parents:
        if (parent / "extensions").exists():
            repo_root = parent
            break
    
    if repo_root is None:
        pytest.fail("Could not find repo root")
    
    files_to_scan = [
        repo_root / "extensions/live_data_pump/pump.py",
    ]
    
    # Forbidden patterns
    forbidden_patterns = [
        "/order\"",
        "listenKey",
        "userDataStream",
        "/fapi",
        "/dapi",
        "/sapi",
    ]
    
    violations = []
    
    for file_path in files_to_scan:
        if not file_path.exists():
            continue
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        for pattern in forbidden_patterns:
            if pattern in content:
                violations.append(f"{file_path.name}: {pattern}")
    
    if violations:
        pytest.fail(f"Forbidden endpoint patterns detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# BONUS: MID/SPREAD CALCULATION DETERMINISM
# ────────────────────────────────────────────────────────────────────────────────

def test_mid_spread_calculation_deterministic():
    """Test mid/spread calculations are deterministic with Decimal."""
    # Test mid price
    mid = models.calculate_mid_price("50000.00", "50100.00")
    assert mid == "50050.00"
    
    # Test spread
    spread = models.calculate_spread("50000.00", "50100.00")
    assert spread == "100.00"
    
    # Test None handling
    assert models.calculate_mid_price(None, "50100.00") is None
    assert models.calculate_spread("50000.00", None) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
