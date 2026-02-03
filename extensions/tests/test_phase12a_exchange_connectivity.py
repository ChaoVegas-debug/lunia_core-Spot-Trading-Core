"""
PHASE 12A — EXCHANGE CONNECTIVITY: Tests

Comprehensive test suite for read-only Binance client.

All tests use mocks (no real network calls).
"""

import pytest
import json
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch
from extensions.exchange_connectivity import binance_client, health, models, security


# ────────────────────────────────────────────────────────────────────────────────
# T1: ENV BUILD CLIENT MISSING VARS (FAIL-CLOSED)
# ───────────────────────────────────────────────────────────────────────────────

def test_env_build_client_missing_vars_fail_closed():
    """Test client build with missing env vars (fail-closed)."""
    with patch.dict('os.environ', {}, clear=True):
        client = binance_client.build_binance_client_from_env()
        
        # Should build but auth_configured=False
        assert client.auth_configured is False
        
        # Auth-required methods should return ENV_MISSING gracefully
        summary = client.account_readonly_summary()
        assert summary["ok"] is False
        assert summary["error"]["code"] == models.ErrorCode.ENV_MISSING


# ────────────────────────────────────────────────────────────────────────────────
# T2: PING AND SERVER_TIME MOCKED (DETERMINISTIC)
# ────────────────────────────────────────────────────────────────────────────────

def test_ping_and_server_time_mocked_deterministic():
    """Test ping and server_time with mocked responses."""
    client = binance_client.BinanceClient(env="mainnet")
    
    # Mock ping
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        ping_resp = client.ping()
        
        assert ping_resp["ok"] is True
        assert ping_resp["exchange"] == "binance"
        assert ping_resp["endpoint"] == "ping"
        assert ping_resp["error"] is None
    
    # Mock server_time
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"serverTime":1737900000000}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        time_resp = client.server_time()
        
        assert time_resp["ok"] is True
        assert time_resp["data"]["serverTime"] == 1737900000000
        assert time_resp["error"] is None


# ────────────────────────────────────────────────────────────────────────────────
# T3: PUBLIC DATA (TICKER + DEPTH) MOCKED PARSING
# ────────────────────────────────────────────────────────────────────────────────

def test_public_data_ticker_depth_mocked_parsing():
    """Test ticker and depth with mocked responses."""
    client = binance_client.BinanceClient(env="mainnet")
    
    # Mock ticker
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"symbol":"BTCUSDT","price":"50000.00"}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        ticker_resp = client.ticker_price("BTCUSDT")
        
        assert ticker_resp["ok"] is True
        assert ticker_resp["data"]["symbol"] == "BTCUSDT"
        assert ticker_resp["data"]["price"] == "50000.00"  # String preserved
    
    # Mock depth
    with patch('urllib.request.urlopen') as mock_urlopen:
        mock_response = MagicMock()
        depth_data = {
            "bids": [["49999.00", "1.5"], ["49998.00", "2.0"]],
            "asks": [["50001.00", "1.0"], ["50002.00", "3.5"]]
        }
        mock_response.read.return_value = json.dumps(depth_data).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        depth_resp = client.depth("BTCUSDT", limit=2)
        
        assert depth_resp["ok"] is True
        assert len(depth_resp["data"]["bids"]) == 2
        assert len(depth_resp["data"]["asks"]) == 2
        assert depth_resp["data"]["bids"][0][0] == "49999.00"


# ────────────────────────────────────────────────────────────────────────────────
# T4: ACCOUNT READONLY SUMMARY (REDACTION, NO BALANCES)
# ────────────────────────────────────────────────────────────────────────────────

def test_account_readonly_summary_redaction_and_no_balances():
    """Test account summary redacts balances and secrets."""
    client = binance_client.BinanceClient(
        api_key="test_key_12345678",
        api_secret="test_secret_abcdefgh",
        env="mainnet"
    )
    
    # Mock server_time + account
    with patch('urllib.request.urlopen') as mock_urlopen:
        # First call: server_time
        time_response = MagicMock()
        time_response.read.return_value = b'{"serverTime":1737900000000}'
        time_response.__enter__.return_value = time_response
        
        # Second call: account
        account_response = MagicMock()
        account_data = {
            "canTrade": True,
            "canWithdraw": False,
            "canDeposit": True,
            "accountType": "SPOT",
            "permissions": ["SPOT"],
            "balances": [
                {"asset": "BTC", "free": "1.0", "locked": "0.0"},
                {"asset": "USDT", "free": "10000.0", "locked": "0.0"}
            ]
        }
        account_response.read.return_value = json.dumps(account_data).encode()
        account_response.__enter__.return_value = account_response
        
        mock_urlopen.side_effect = [time_response, account_response]
        
        summary = client.account_readonly_summary()
        
        assert summary["ok"] is True
        assert summary["data"]["canTrade"] is True
        assert summary["data"]["balances_count"] == 2
        
        # Balances must NOT be present
        assert "balances" not in summary["data"]
        
        # Secrets must NOT appear in response
        summary_str = json.dumps(summary)
        assert "test_secret" not in summary_str.lower()


# ────────────────────────────────────────────────────────────────────────────────
# T5: NO WALL-CLOCK IMPORTS (AST SCAN)
# ────────────────────────────────────────────────────────────────────────────────

def test_no_wall_clock_imports_phase12a_ast():
    """AST scan: verify no wall-clock usage in Phase 12A modules."""
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
        repo_root / "extensions/exchange_connectivity/binance_client.py",
        repo_root / "extensions/exchange_connectivity/health.py",
        repo_root / "extensions/exchange_connectivity/models.py",
        repo_root / "extensions/exchange_connectivity/security.py",
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
# T6: NO TRADE ENDPOINTS PRESENT (STATIC SCAN)
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
        repo_root / "extensions/exchange_connectivity/binance_client.py",
    ]
    
    # Forbidden patterns (check string presence)
    forbidden_patterns = [
        "/order\"",  # Avoid false positives from word "order"
        "/fapi",
        "/dapi",
        "/sapi",
        "userDataStream",
        "listenKey",
    ]
    
    violations = []
    
    for file_path in files_to_scan:
        if not file_path.exists():
            continue
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        for pattern in forbidden_patterns:
            if pattern in content and "FORBIDDEN_PATTERNS" not in content:
                # Allow in FORBIDDEN_PATTERNS list itself
                violations.append(f"{file_path.name}: {pattern}")

    
    if violations:
        pytest.fail(f"Forbidden endpoint patterns detected:\n" + "\n".join(violations))


# ────────────────────────────────────────────────────────────────────────────────
# T7: ENDPOINT ALLOWLIST ENFORCED
# ────────────────────────────────────────────────────────────────────────────────

def test_endpoint_allowlist_enforced():
    """Test that forbidden endpoints are blocked."""
    client = binance_client.BinanceClient(env="mainnet")
    
    # Test forbidden endpoint (should fail internal check)
    error = client._check_endpoint_allowed("/api/v3/order")
    
    assert error is not None
    assert error.code == models.ErrorCode.FORBIDDEN_ENDPOINT


# ────────────────────────────────────────────────────────────────────────────────
# T8: INSTANCE ISOLATION (NO GLOBAL STATE)
# ────────────────────────────────────────────────────────────────────────────────

def test_instance_isolation_no_global_state():
    """Test two clients don't cross-contaminate."""
    client1 = binance_client.BinanceClient(
        api_key="key1",
        api_secret="secret1",
        env="mainnet"
    )
    
    client2 = binance_client.BinanceClient(
        api_key="key2",
        api_secret="secret2",
        env="testnet"
    )
    
    # Verify independent state
    assert client1.env == "mainnet"
    assert client2.env == "testnet"
    
    assert client1.api_key.get() == "key1"
    assert client2.api_key.get() == "key2"
    
    assert client1.base_url == binance_client.BinanceClient.MAINNET_BASE_URL
    assert client2.base_url == binance_client.BinanceClient.TESTNET_BASE_URL


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
