"""
PHASE 12A — EXCHANGE CONNECTIVITY: Health Surface

Connectivity health aggregator for UI Airlock.
"""

from typing import Dict, Any
from .binance_client import BinanceClient


def get_connectivity_health(client: BinanceClient, *, symbol_probe: str = "BTCUSDT") -> Dict[str, Any]:
    """
    Get comprehensive connectivity health.
    
    Args:
        client: BinanceClient instance
        symbol_probe: Symbol to probe for public data (default "BTCUSDT")
    
    Returns:
        Health dict with ok/rest/auth/public_data sections
    """
    health = {
        "ok": True,  # Overall health (updated below)
        "exchange": "binance",
        "env": client.env,
        "rest": {
            "ping_ok": False,
            "server_time_ok": False,
            "last_error": None,
        },
        "auth": {
            "configured": client.auth_configured,
            "account_ok": False,
            "summary": None,
            "last_error": None,
        },
        "public_data": {
            "symbol": symbol_probe,
            "ticker_ok": False,
            "depth_ok": False,
            "last_error": None,
        },
    }
    
    # Test REST connectivity (ping + server_time)
    try:
        ping_resp = client.ping()
        health["rest"]["ping_ok"] = ping_resp["ok"]
        if not ping_resp["ok"]:
            health["rest"]["last_error"] = ping_resp.get("error")
            health["ok"] = False
    except Exception as e:
        health["rest"]["last_error"] = {"code": "EXCEPTION", "message": str(e)}
        health["ok"] = False
    
    try:
        time_resp = client.server_time()
        health["rest"]["server_time_ok"] = time_resp["ok"]
        if not time_resp["ok"]:
            health["rest"]["last_error"] = time_resp.get("error")
            health["ok"] = False
    except Exception as e:
        health["rest"]["last_error"] = {"code": "EXCEPTION", "message": str(e)}
        health["ok"] = False
    
    # Test auth (only if configured)
    if client.auth_configured:
        try:
            account_resp = client.account_readonly_summary()
            health["auth"]["account_ok"] = account_resp["ok"]
            if account_resp["ok"]:
                health["auth"]["summary"] = account_resp["data"]
            else:
                health["auth"]["last_error"] = account_resp.get("error")
                health["ok"] = False
        except Exception as e:
            health["auth"]["last_error"] = {"code": "EXCEPTION", "message": str(e)}
            health["ok"] = False
    
    # Test public data (ticker + depth)
    try:
        ticker_resp = client.ticker_price(symbol_probe)
        health["public_data"]["ticker_ok"] = ticker_resp["ok"]
        if not ticker_resp["ok"]:
            health["public_data"]["last_error"] = ticker_resp.get("error")
            health["ok"] = False
    except Exception as e:
        health["public_data"]["last_error"] = {"code": "EXCEPTION", "message": str(e)}
        health["ok"] = False
    
    try:
        depth_resp = client.depth(symbol_probe, limit=5)
        health["public_data"]["depth_ok"] = depth_resp["ok"]
        if not depth_resp["ok"]:
            health["public_data"]["last_error"] = depth_resp.get("error")
            health["ok"] = False
    except Exception as e:
        health["public_data"]["last_error"] = {"code": "EXCEPTION", "message": str(e)}
        health["ok"] = False
    
    return health
