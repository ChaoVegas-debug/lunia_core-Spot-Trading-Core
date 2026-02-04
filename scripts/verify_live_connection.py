
import sys
import logging
from pathlib import Path
from flask import Flask

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("live_verifier")

# Path Setup
sys.path.append(str(Path.cwd() / "lunia_core"))

try:
    from lunia_core.app.services.api.flask_app import app, agent
    from lunia_core.app.core.exchange.binance_spot import BinanceSpot
    from lunia_core.app.services.security import credentials_service
except ImportError as e:
    print(f"Import Failed: {e}")
    sys.exit(1)

def verify_live():
    print("\n--- LIVE CONNECTION VERIFICATION ---")
    
    # 1. Initialize Agent (Forces Load of .secrets.json)
    # We simulate app boot
    with app.app_context():
        # Force reload credentials
        creds = credentials_service.load_credentials("binance")
        print(f"[SETUP] Credentials from {creds.source}: Valid={creds.is_valid_format} Testnet={creds.is_testnet}")
        
        if not creds.is_valid_format:
            print("!!! FAILURE: INVALID CREDENTIALS !!!")
            sys.exit(1)
            
        # Re-initialize client manually to be sure
        client = BinanceSpot(
            api_key=creds.api_key,
            api_secret=creds.api_secret,
            use_testnet=creds.is_testnet,
            mock=False # EXPLICIT LIVE MODE
        )
        
        print(f"[SETUP] Client initialized. Mock={client.mock} BaseUrl={client.base_url}")
        
        if client.mock:
             print("!!! FAILURE: Client fell back to MOCK !!!")
             # But wait, if keys are valid, mock should be False.
             sys.exit(1)
             
        # 2. Test Connection (Ping + Time)
        try:
            client._sync_time()
            print(f"[TEST] Time Sync OK. Offset={client.time_offset}ms")
        except Exception as e:
            print(f"[TEST] Time Sync Failed: {e}")
            
        # 3. Test Balances (The Real Deal)
        print("[ACTION] Fetching Live Balances...")
        try:
            balances = client.get_balances(force_real=True) # Explicit force
            print(f"[SUCCESS] Balances Fetched. Count={len(balances)}")
            print("[SAMPLE]", list(balances.items())[:3])
            
            # Check USDT specifically
            usdt = balances.get("USDT", {"free": 0, "locked": 0})
            print(f"[ASSET] USDT: {usdt}")
            
        except Exception as e:
            print(f"!!! LIVE FETCH FAILED !!! {e}")
            sys.exit(1)

if __name__ == "__main__":
    verify_live()
