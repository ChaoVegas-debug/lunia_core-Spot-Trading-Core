import requests
import sys
import json
from pathlib import Path

BASE_URL = "http://127.0.0.1:8080"
HEADERS = {
    "Authorization": "Bearer dev-token",
    "X-Admin-Token": "admin-ops-key-123",
    "X-Data-Source": "REAL"
}

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def verify_combat_readiness():
    log("--- STARTING COMBAT READINESS VERIFICATION ---")

    # 1. Check Debug State (Must NOT be Mock)
    try:
        res = requests.get(f"{BASE_URL}/api/exchanges/debug", headers=HEADERS, timeout=5)
        if res.status_code != 200:
            log(f"Debug endpoint failed: {res.status_code}", "FAIL")
            sys.exit(1)
        
        debug_data = res.json()
        log(f"Debug State: {json.dumps(debug_data, indent=2)}")
        
        if debug_data.get("mock") is True:
            log("CRITICAL FAILURE: System is in MOCK mode!", "FAIL")
            sys.exit(1)
            
        if not debug_data.get("key_present"):
            log("CRITICAL FAILURE: No API Key present!", "FAIL")
            sys.exit(1)
            
        log("✅ System is in LIVE CONFIGURATION (Mock=False)")
        
    except Exception as e:
        log(f"Debug check failed: {e}", "FAIL")
        sys.exit(1)

    # 2. Check Live Balances
    try:
        log("Attemping REAL Balance Fetch...")
        res = requests.get(f"{BASE_URL}/balances", headers=HEADERS, timeout=10)
        
        if res.status_code == 401:
             log("Auth Failed (401). This is FAIL-CLOSED behavior (Good if keys invalid, Bad if valid).", "WARN")
             # If keys are valid (we injected them), this shouldn't happen unless IP block.
             log(f"Response: {res.text}", "WARN")
             if "Invalid API-key" in res.text:
                 sys.exit(1) 
        
        if res.status_code != 200:
             log(f"Balance fetch failed: {res.status_code} {res.text}", "FAIL")
             sys.exit(1)
             
        data = res.json()
        source = data.get("source")
        env = data.get("env")
        
        if source != "REAL":
            log(f"CRITICAL FAILURE: Returned Source is {source}", "FAIL")
            sys.exit(1)
            
        if env != "MAINNET":
            log(f"CRITICAL FAILURE: Environment is {env}", "FAIL")
            sys.exit(1)
            
        # Check Balances
        balances = data.get("balances", [])
        log(f"✅ Balances Fetched: {len(balances)} assets found.")
        
        # Look for the BTC/USDT we saw earlier
        btc = next((b for b in balances if b['asset'] == 'BTC'), None)
        usdt = next((b for b in balances if b['asset'] == 'USDT'), None)
        
        if btc: log(f"   BTC: {btc['free']}")
        if usdt: log(f"   USDT: {usdt['free']}")
        
        log("✅ POSITIVE TEST PASSED: System is HOT and REAL.")

        # --- NEGATIVE TESTING ---
        log("\n--- STARTING NEGATIVE TEST (MISSING/INVALID CREDENTIALS) ---")
        log("1. Moving valid .secrets.json to .secrets.json.bak")
        secrets_path = Path(".secrets.json")
        backup_path = Path(".secrets.json.bak")
        
        if secrets_path.exists():
             secrets_path.rename(backup_path)
        
        try:
             log("2. Restarting backend with INVALID Env Keys...")
             
             import subprocess
             subprocess.run("pkill -9 -f flask_app", shell=True)
             
             # Start with valid-length but garbage keys to bypass length check if we wanted, 
             # but since file is gone, even short keys will result in "No Credentials Found" -> Fail Closed.
             # We use short keys to ensure it doesn't try to use them as valid.
             cmd = "export BINANCE_API_KEY='invalid'; export BINANCE_API_SECRET='invalid'; ./scripts/start_prod.sh"
             subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
             
             import time
             log("3. Waiting for backend restart (Negative Mode)...")
             time.sleep(8)
             
             # Verify Fail-Closed
             try:
                  res = requests.get(f"{BASE_URL}/balances", headers=HEADERS, timeout=5)
                  if res.status_code == 200:
                       data = res.json()
                       # Check if it returned mock balances
                       if "USDT" in [b['asset'] for b in data.get("balances",[])]:
                            usdt_bal = next((b for b in data['balances'] if b['asset'] == 'USDT'), {})
                            if usdt_bal.get("free") == 1000.0:
                                 log("CRITICAL FAILURE: System fell back to MOCK balances (1000 USDT) despite Mainnet!", "FAIL")
                                 sys.exit(1)
                       
                       log(f"CRITICAL FAILURE: Backend returned 200 OK with Invalid Keys! Response: {res.text[:100]}", "FAIL")
                       sys.exit(1)
                  else:
                       log(f"✅ NEGATIVE TEST PASSED: Backend rejected invalid keys with {res.status_code} (Fail-Closed).")
                       
             except Exception as e:
                  log(f"✅ NEGATIVE TEST PASSED: Connection/Req failed as expected ({e})", "INFO")

        finally:
             if backup_path.exists():
                  log("4. Restoring .secrets.json...")
                  backup_path.rename(secrets_path)
        
        # Cleanup: Restart with GOOD keys
        log("Restoring LIVE Configuration...")
        subprocess.run("pkill -9 -f flask_app", shell=True)
        subprocess.Popen("./scripts/start_prod.sh", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
        log("✅ System Restored.")

    except Exception as e:
        log(f"Balance check failed: {e}", "FAIL")
        sys.exit(1)

if __name__ == "__main__":
    verify_combat_readiness()
