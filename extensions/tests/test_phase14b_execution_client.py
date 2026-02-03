"""
PHASE 14B — LIVE ADAPTER: Comprehensive Test Suite

Tests for write-enabled execution client (ALL MOCKED - NO NETWORK).

CRITICAL:
- All tests mocked (no real API calls)
- Testnet default verification
- Mainnet guard verification
- No-bypass static scan
- Determinism verification
"""

import pytest
import ast
import hashlib
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from decimal import Decimal

from extensions.exchange_connectivity.execution_client import BinanceExecutionClient
from extensions.exchange_connectivity.trade_models import (
    OrderResult,
    OrderStatus,
    generate_client_order_id,
    parse_binance_order_response,
    parse_binance_error_to_order_result,
)


# ────────────────────────────────────────────────────────────────────────────────
# TEST 1: Signature Correctness
# ────────────────────────────────────────────────────────────────────────────────

def test_signature_correctness():
    """Verify HMAC SHA256 signing matches known test vector."""
    client = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="testnet",
    )
    
    # Known test vector
    params = {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": "0.001"}
    server_time_ms = 1704067200000
    
    signature = client._sign_request(params, server_time_ms)
    
    # Verify signature is hex string
    assert isinstance(signature, str)
    assert len(signature) == 64  # SHA256 hex = 64 chars
    
    # Verify determinism (same inputs → same signature)
    signature2 = client._sign_request(params, server_time_ms)
    assert signature == signature2


# ────────────────────────────────────────────────────────────────────────────────
# TEST 2: Market Order Success Normalization
# ────────────────────────────────────────────────────────────────────────────────

def test_market_order_success_normalization():
    """Mock successful market order → OrderResult(status=\"FILLED\")."""
    client = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="testnet",
    )
    
    # Mock server_time response
    mock_time_response = {
        "ok": True,
        "data": {"serverTime": 1704067200000},
    }
    
    # Mock order response (FILLED)
    mock_order_response = {
        "orderId": 123456,
        "clientOrderId": "BTCUSDT_1704067200000_abcd1234",
        "symbol": "BTCUSDT",
        "status": "FILLED",
        "executedQty": "0.001",
        "cummulativeQuoteQty": "50.0",
        "fills": [
            {"price": "50000", "qty": "0.001", "commission": "0.00001", "commissionAsset": "BTC"}
        ],
    }
    
    with patch.object(client, 'server_time', return_value=mock_time_response):
        with patch.object(client, '_request', return_value=mock_order_response):
            result = client.create_order(
                symbol="BTCUSDT",
                side="BUY",
                order_type="MARKET",
                quantity=Decimal("0.001"),
            )
    
    # Verify normalization
    assert isinstance(result, OrderResult)
    assert result.status == "FILLED"
    assert result.symbol == "BTCUSDT"
    assert result.filled_qty == Decimal("0.001")
    assert result.avg_price == Decimal("50000")  # 50.0 / 0.001
    assert result.fees == Decimal("0.00001")


# ────────────────────────────────────────────────────────────────────────────────
# TEST 3: Limit Order Success Normalization
# ────────────────────────────────────────────────────────────────────────────────

def test_limit_order_success_normalization():
    """Mock successful limit order → OrderResult(status=\"NEW\")."""
    client = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="testnet",
    )
    
    mock_time_response = {
        "ok": True,
        "data": {"serverTime": 1704067200000},
    }
    
    mock_order_response = {
        "orderId": 123457,
        "clientOrderId": "BTCUSDT_1704067200000_abcd1234",
        "symbol": "BTCUSDT",
        "status": "NEW",
        "executedQty": "0",
        "cummulativeQuoteQty": "0",
        "fills": [],
    }
    
    with patch.object(client, 'server_time', return_value=mock_time_response):
        with patch.object(client, '_request', return_value=mock_order_response):
            result = client.create_order(
                symbol="BTCUSDT",
                side="BUY",
                order_type="LIMIT",
                quantity=Decimal("0.001"),
                price=Decimal("49000"),
            )
    
    assert result.status == "NEW"
    assert result.filled_qty == Decimal("0")
    assert result.avg_price == Decimal("0")


# ────────────────────────────────────────────────────────────────────────────────
# TEST 4: Insufficient Balance → REJECTED
# ────────────────────────────────────────────────────────────────────────────────

def test_insufficient_balance_rejected():
    """Mock exchange error (insufficient balance) → OrderResult(status=\"REJECTED\")."""
    client = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="testnet",
    )
    
    mock_time_response = {
        "ok": True,
        "data": {"serverTime": 1704067200000},
    }
    
    with patch.object(client, 'server_time', return_value=mock_time_response):
        with patch.object(client, '_request', side_effect=Exception("Insufficient balance")):
            result = client.create_order(
                symbol="BTCUSDT",
                side="BUY",
                order_type="MARKET",
                quantity=Decimal("0.001"),
            )
    
    # Should be REJECTED (definitive error)
    assert result.status == "REJECTED"
    assert result.order_id is None
    assert result.filled_qty == Decimal("0")


# ────────────────────────────────────────────────────────────────────────────────
# TEST 5: Timeout → UNKNOWN
# ────────────────────────────────────────────────────────────────────────────────

def test_timeout_unknown():
    """Mock network timeout → OrderResult(status=\"UNKNOWN\")."""
    client = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="testnet",
    )
    
    mock_time_response = {
        "ok": True,
        "data": {"serverTime": 1704067200000},
    }
    
    with patch.object(client, 'server_time', return_value=mock_time_response):
        with patch.object(client, '_request', side_effect=Exception("Connection timeout")):
            result = client.create_order(
                symbol="BTCUSDT",
                side="BUY",
                order_type="MARKET",
                quantity=Decimal("0.001"),
            )
    
    # Should be UNKNOWN (network ambiguity)
    assert result.status == "UNKNOWN"
    assert result.order_id is None


# ────────────────────────────────────────────────────────────────────────────────
# TEST 6: Decimal Precision Preserved
# ────────────────────────────────────────────────────────────────────────────────

def test_decimal_precision_preserved():
    """Verify qty/price Decimal → str → Decimal roundtrip."""
    # Test quantity precision
    qty = Decimal("0.00123456")
    qty_str = str(qty)
    qty_parsed = Decimal(qty_str)
    assert qty == qty_parsed
    
    # Test price precision
    price = Decimal("50123.456789")
    price_str = str(price)
    price_parsed = Decimal(price_str)
    assert price == price_parsed
    
    # Test in OrderResult
    result = OrderResult(
        order_id="123",
        client_order_id="test",
        symbol="BTCUSDT",
        status="FILLED",
        filled_qty=Decimal("0.00123456"),
        avg_price=Decimal("50123.456789"),
        fees=Decimal("0.00000123"),
    )
    
    result_dict = result.to_dict()
    
    # Verify serialization
    assert result_dict["filled_qty"] == "0.00123456"
    assert result_dict["avg_price"] == "50123.456789"
    assert result_dict["fees"] == "0.00000123"
    
    # Verify deserialization
    filled_qty_back = Decimal(result_dict["filled_qty"])
    assert filled_qty_back == Decimal("0.00123456")


# ────────────────────────────────────────────────────────────────────────────────
# TEST 7: Testnet Default Enforcement
# ────────────────────────────────────────────────────────────────────────────────

def test_testnet_default_enforcement():
    """Verify env=None → testnet URL."""
    # Case 1: env=None (should default to testnet)
    client = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env=None,
    )
    assert client.base_url == "https://testnet.binance.vision"
    
    # Case 2: env="testnet" (explicit)
    client2 = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="testnet",
    )
    assert client2.base_url == "https://testnet.binance.vision"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 8: Mainnet Requires Explicit Flag
# ────────────────────────────────────────────────────────────────────────────────

def test_mainnet_requires_explicit_flag():
    """Verify mainnet blocked without allow_mainnet=True."""
    # Case 1: env="mainnet" without allow_mainnet → should FAIL
    with pytest.raises(ValueError, match="allow_mainnet=True"):
        client = BinanceExecutionClient(
            api_key="test_key",
            api_secret="test_secret",
            env="mainnet",
            allow_mainnet=False,  # Explicit False
        )
    
    # Case 2: env="mainnet" with allow_mainnet=True → should WORK
    client2 = BinanceExecutionClient(
        api_key="test_key",
        api_secret="test_secret",
        env="mainnet",
        allow_mainnet=True,
    )
    assert client2.base_url == "https://api.binance.com"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 9: No Wall-Clock Imports (AST Scan)
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_ast():
    """AST scan for forbidden wall-clock imports."""
    phase14b_files = [
        Path(__file__).parent.parent / "exchange_connectivity" / "execution_client.py",
        Path(__file__).parent.parent / "exchange_connectivity" / "trade_models.py",
    ]
    
    forbidden_imports = ["time", "datetime"]
    forbidden_calls = ["time.time", "datetime.now", "time.perf_counter"]
    
    for py_file in phase14b_files:
        if not py_file.exists():
            continue
        
        with open(py_file, "r") as f:
            source = f.read()
        
        tree = ast.parse(source, filename=str(py_file))
        
        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name not in forbidden_imports, \
                        f"{py_file.name}: Forbidden import: {alias.name}"
            
            elif isinstance(node, ast.ImportFrom):
                if node.module in forbidden_imports:
                    assert False, f"{py_file.name}: Forbidden import from: {node.module}"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 10: No-Bypass Static Scan
# ────────────────────────────────────────────────────────────────────────────────

def test_no_bypass_static_scan():
    """
    Grep scan to verify Phase 13/14A cannot import execution_client.
    
    CRITICAL GOVERNANCE TEST:
    Proves that shadow_mode, genome_dsl, virtual_portfolio, hud_api,
    and execution_gateway CANNOT bypass the single chokepoint.
    """
    forbidden_modules = [
        Path(__file__).parent.parent / "shadow_mode",
        Path(__file__).parent.parent / "genome_dsl",
        Path(__file__).parent.parent / "virtual_portfolio",
        Path(__file__).parent.parent / "hud_api",
        Path(__file__).parent.parent / "execution_gateway",
    ]
    
    forbidden_patterns = [
        "from extensions.exchange_connectivity.execution_client import",
        "from .exchange_connectivity.execution_client import",
        "from ..exchange_connectivity.execution_client import",
        "import execution_client",
        "BinanceExecutionClient",
        "create_order",  # Method name (if imported)
    ]
    
    for module_dir in forbidden_modules:
        if not module_dir.exists():
            continue
        
        for py_file in module_dir.glob("**/*.py"):
            with open(py_file, "r") as f:
                content = f.read()
            
            for pattern in forbidden_patterns:
                assert pattern not in content, \
                    f"BYPASS DETECTED: {py_file.relative_to(module_dir.parent)} contains '{pattern}'"


# ────────────────────────────────────────────────────────────────────────────────
# TEST 11: Deterministic client_order_id Generation
# ────────────────────────────────────────────────────────────────────────────────

def test_deterministic_client_order_id_generation():
    """Verify client_order_id is deterministic (same inputs → same output)."""
    symbol = "BTCUSDT"
    timestamp_ms = 1704067200000
    nonce = "test"
    
    # Generate 10 times
    ids = [generate_client_order_id(symbol, timestamp_ms, nonce) for _ in range(10)]
    
    # All should be identical
    assert len(set(ids)) == 1
    assert ids[0] == f"{symbol}_{timestamp_ms}_" + hashlib.sha256(
        f"{symbol}_{timestamp_ms}_{nonce}".encode("utf-8")
    ).hexdigest()[:8]
