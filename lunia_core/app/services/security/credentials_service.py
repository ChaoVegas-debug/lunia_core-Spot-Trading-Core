"""
Canonical Credential Service for LUNIA Core.
Enforces Single Source of Truth for exchange credentials.
"""
import os
import json
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any

from lunia_core.app.services.api.config import LOG_DIR
from lunia_core.app.compat.requests import requests

# Canonical Store Path (Absolute)
CREDENTIALS_FILE = LOG_DIR.parent / ".secrets.json"

logger = logging.getLogger(__name__)

@dataclass
class ExchangeCredentials:
    api_key: str
    api_secret: str
    is_testnet: bool
    source: str  # "ENV", "FILE", "NONE"
    is_valid_format: bool
    validation_error: Optional[str] = None

    @property
    def key_hash(self) -> str:
        """Forensic fingerprint of the key."""
        if not self.api_key:
            return "empty"
        return hashlib.sha256(self.api_key.encode()).hexdigest()[:8]

    @property
    def short_len(self) -> str:
        """Forensic length description."""
        return f"K={len(self.api_key)}/S={len(self.api_secret)}"


def _validate_format(api_key: str, api_secret: str) -> Tuple[bool, Optional[str]]:
    """Strict format validation for Binance keys."""
    if not api_key or not api_secret:
        return False, "Missing Key or Secret"
    
    # Binance Keys are ~64 chars. 
    # Reject anything obviously truncated (< 32 chars).
    if len(api_key) < 32:
        return False, f"API Key too short ({len(api_key)} chars). Expected ~64."
    if len(api_secret) < 32:
        return False, f"API Secret too short ({len(api_secret)} chars). Expected ~64."
    
    return True, None


def load_credentials(exchange_id: str = "binance") -> ExchangeCredentials:
    """
    Load credentials with strict precedence:
    1. ENV VARS (if valid format)
    2. SECRETS FILE (if valid format)
    3. ENV VARS (fallback even if invalid, for transparency)
    4. SECRETS FILE (fallback even if invalid, for transparency)
    """
    # 1. Check Env
    env_key = os.getenv("BINANCE_API_KEY", "").strip()
    env_secret = os.getenv("BINANCE_API_SECRET", "").strip()
    env_testnet = os.getenv("BINANCE_USE_TESTNET", "false").lower() == "true"
    
    env_valid, env_err = _validate_format(env_key, env_secret)
    
    if env_valid:
        logger.info(f"[CREDENTIALS] Loaded from ENV. {env_err or 'Valid'}.")
        return ExchangeCredentials(env_key, env_secret, env_testnet, "ENV", True)

    # 2. Check File
    file_key = ""
    file_secret = ""
    file_testnet = False
    
    try:
        if CREDENTIALS_FILE.exists():
            with open(CREDENTIALS_FILE, "r") as f:
                data = json.load(f)
                exch_data = data.get(exchange_id, {})
                file_key = exch_data.get("api_key", "").strip()
                file_secret = exch_data.get("api_secret", "").strip()
                file_testnet = exch_data.get("is_testnet", False)
    except Exception as e:
        logger.error(f"[CREDENTIALS] Failed to read secrets file: {e}")

    file_valid, file_err = _validate_format(file_key, file_secret)

    if file_valid:
        logger.info(f"[CREDENTIALS] Loaded from FILE ({CREDENTIALS_FILE}). Valid.")
        return ExchangeCredentials(file_key, file_secret, file_testnet, "FILE", True)

    # 3. Fallbacks (Return invalid creds but marked as such, prefer file if it exists and env is empty)
    if file_key:
        logger.warning(f"[CREDENTIALS] Loaded INVALID keys from FILE. {file_err}")
        return ExchangeCredentials(file_key, file_secret, file_testnet, "FILE_INVALID", False, file_err)
    
    if env_key:
        logger.warning(f"[CREDENTIALS] Loaded INVALID keys from ENV. {env_err}")
        return ExchangeCredentials(env_key, env_secret, env_testnet, "ENV_INVALID", False, env_err)

    return ExchangeCredentials("", "", False, "NONE", False, "No credentials found")


def save_credentials(exchange_id: str, api_key: str, api_secret: str, is_testnet: bool) -> ExchangeCredentials:
    """
    Atomic save to secrets file.
    Validates format BEFORE saving to avoid polluting disk with garbage.
    """
    valid, err = _validate_format(api_key, api_secret)
    if not valid:
        raise ValueError(f"Invalid Credentials Format: {err}")

    # Load existing to preserve other exchanges
    full_data = {}
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r") as f:
                full_data = json.load(f)
        except Exception:
            full_data = {}

    full_data[exchange_id] = {
        "api_key": api_key,
        "api_secret": api_secret,
        "is_testnet": is_testnet,
        "updated_at": _current_iso_time()
    }

    # Atomic Write
    temp_file = CREDENTIALS_FILE.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump(full_data, f, indent=2)
    
    os.replace(temp_file, CREDENTIALS_FILE)
    
    logger.info(f"[CREDENTIALS] Saved {exchange_id} to {CREDENTIALS_FILE}. Valid=True")
    return load_credentials(exchange_id) # Reload to confirm

def test_connection_forensic(creds: ExchangeCredentials) -> Dict[str, Any]:
    """
    Perform a forensic connection test.
    Returns structured diagnostic data.
    """
    if not creds.is_valid_format:
        return {
            "status": "error",
            "code": "INVALID_FORMAT",
            "message": creds.validation_error or "Credentials malformed",
            "source": creds.source,
            "key_len": len(creds.api_key),
            "signature_check": "SKIPPED"
        }

    base_url = "https://testnet.binance.vision" if creds.is_testnet else "https://api.binance.com"
    session = requests.Session()
    session.headers.update({"X-MBX-APIKEY": creds.api_key})
    
    result = {
        "status": "unknown",
        "env": "TESTNET" if creds.is_testnet else "MAINNET",
        "base_url": base_url,
        "public_ping": "pending",
        "auth_ping": "pending",
        "latency_ms": 0
    }

    # 1. Public Ping
    try:
        t0 = _millis()
        r = session.get(f"{base_url}/api/v3/ping", timeout=5)
        r.raise_for_status()
        lat = _millis() - t0
        result["public_ping"] = "ok"
        result["latency_ms"] = lat
    except Exception as e:
        result["public_ping"] = f"failed: {str(e)}"
        result["status"] = "network_error"
        result["message"] = f"Cannot reach Binance: {str(e)}"
        return result

    # 2. Authenticated Account Check (The Source of Truth)
    try:
        # Sign
        import time
        ts = int(time.time() * 1000)
        params = {"timestamp": ts, "recvWindow": 5000}
        query = "&".join(f"{k}={v}" for k,v in params.items())
        sig = hmac.new(creds.api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()
        
        r = session.get(f"{base_url}/api/v3/account", params={**params, "signature": sig}, timeout=5)
        
        if r.status_code == 200:
            result["auth_ping"] = "ok"
            result["status"] = "ok"
            result["message"] = "Connected and Authenticated"
            # Maybe return permissions?
            data = r.json()
            result["permissions"] = {
                "canTrade": data.get("canTrade"),
                "canWithdraw": data.get("canWithdraw"),
                "accountType": data.get("accountType")
            }
        else:
            result["auth_ping"] = f"failed: {r.status_code}"
            result["status"] = "auth_error"
            try:
                err = r.json()
                result["upstream_code"] = err.get("code")
                result["upstream_msg"] = err.get("msg")
                result["message"] = f"Binance Error: {err.get('msg')} (Code {err.get('code')})"
            except:
                 result["message"] = f"HTTP {r.status_code}"

    except Exception as e:
        result["status"] = "system_error"
        result["message"] = str(e)

    return result

def _current_iso_time():
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"

def _millis():
    import time
    return int(time.time() * 1000)
