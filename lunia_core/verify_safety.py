
import requests
import time
import uuid
import json

BASE_URL = "http://127.0.0.1:8080"
ADMIN_EMAIL = "admin@example.com"
ADMIN_PASS = "admin123"
OPS_TOKEN = "dev-ops-token"

session = requests.Session()

def log(msg, status="INFO"):
    print(f"[{status}] {msg}")

def login():
    log("Logging in...")
    try:
        res = session.post(f"{BASE_URL}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        if res.status_code != 200:
            log(f"Login Failed: {res.text}", "FAIL")
            if "invalid_credentials" in res.text:
                 session.headers.update({"X-OPS-TOKEN": OPS_TOKEN})
                 return
            exit(1)
        token = res.json().get("access_token")
        session.headers.update({"Authorization": f"Bearer {token}", "X-OPS-TOKEN": OPS_TOKEN})
        log("Login Success", "PASS")
    except Exception as e:
        log(f"Login Exception: {e}", "FAIL")
        exit(1)

def test_stop():
    log("Test 1: Global STOP")
    # 1. Enable STOP
    key = str(uuid.uuid4())
    res = session.post(f"{BASE_URL}/ops/state", json={"global_stop": True}, headers={"Idempotency-Key": key})
    if res.status_code != 200:
        log(f"Failed to set STOP: {res.text}", "FAIL")
        return
    log("STOP Engaged", "PASS")
    
    # 2. Try Restricted Action
    trade = {
        "proposal": {
            "exchange_id": "binance",
            "symbol": "BTCUSDT", 
            "side": "BUY", 
            "amount_usd": 100, 
            "strategy_id": "manual",
            "confirm_deadline": time.time() + 60
        },
        "confirmed": True
    }
    res = session.post(f"{BASE_URL}/spot/manual/execute", json=trade)
    if res.status_code == 409 and res.json().get("code") == "STOP_ACTIVE":
        log("Stopped Action Rejected (409)", "PASS")
    else:
        log(f"Stopped Action NOT Rejected properly: {res.status_code} {res.text}", "FAIL")

    # 3. Disable STOP
    res = session.post(f"{BASE_URL}/ops/state", json={"global_stop": False}, headers={"Idempotency-Key": str(uuid.uuid4())})
    if res.status_code == 200:
        log("STOP Released", "PASS")

def test_undo():
    log("Test 2: Universal Undo (Strategy)")
    # 1. Get current state
    res = session.get(f"{BASE_URL}/spot/strategies")
    if res.status_code != 200:
         log(f"Get Strategies Failed: {res.status_code} {res.text}", "FAIL")
         return
    
    try:
        original = res.json()
    except:
        log(f"Get Strategies JSON Decode Failed. Body: {res.text}", "FAIL")
        return

    if not original:
        log("No strategies found to test", "WARN")
        return

    target_id = original[0]['id']
    original_weight = original[0]['weight']
    
    # 2. Modify
    new_weight = 0.99
    payload = [{"id": s['id'], "enabled": s['enabled'], "weight": (new_weight if s['id'] == target_id else s['weight'])} for s in original]
    
    key = str(uuid.uuid4())
    res = session.post(f"{BASE_URL}/spot/strategies", json=payload, headers={"Idempotency-Key": key})
    
    if res.status_code != 200:
        log(f"Update failed: {res.status_code} {res.text}", "FAIL")
        return

    try:
        data = res.json()
    except:
        log(f"Update JSON Decode Failed. Body: {res.text}", "FAIL")
        return

    if not data.get("undo_token"):
        log("No undo_token returned", "FAIL")
        return
    
    undo_token = data.get("undo_token")
    log(f"Got Undo Token: {undo_token}", "PASS")
    
    # Verify Change
    res = session.get(f"{BASE_URL}/spot/strategies")
    curr_weight = next(s['weight'] for s in res.json() if s['id'] == target_id)
    if curr_weight != new_weight:
        log(f"Change not applied? Got {curr_weight}", "FAIL")
    
    # 3. Undo
    res = session.post(f"{BASE_URL}/ops/undo", json={"token": undo_token})
    if res.status_code == 200:
        log("Undo Request Success", "PASS")
    else:
        log(f"Undo Failed: {res.text}", "FAIL")
        
    # 4. Verify Revert
    res = session.get(f"{BASE_URL}/spot/strategies")
    reverted_weight = next(s['weight'] for s in res.json() if s['id'] == target_id)
    if abs(reverted_weight - original_weight) < 0.001:
        log("State Reverted Successfully", "PASS")
    else:
        log(f"State NOT Reverted. Got {reverted_weight}, Expected {original_weight}", "FAIL")

def test_idempotency():
    log("Test 3: Persistent Idempotency")
    key = str(uuid.uuid4())
    payload = {"global_stop": False} 
    
    # First Call
    res1 = session.post(f"{BASE_URL}/ops/state", json=payload, headers={"Idempotency-Key": key})
    
    # Second Call
    res2 = session.post(f"{BASE_URL}/ops/state", json=payload, headers={"Idempotency-Key": key})
    
    if res1.text == res2.text and res1.status_code == res2.status_code:
        log("Response Identical", "PASS")
    else:
        log("Idempotency Mismatch", "FAIL")

def test_ttl():
    log("Test 4: TTL Enforcement")
    # Execute with expired deadline
    expired_time = int(time.time() - 10)
    trade = {
        "proposal": {
            "exchange_id": "binance",
            "symbol": "BTCUSDT", 
            "side": "BUY", 
            "amount_usd": 100, 
            "strategy_id": "manual",
            "confirm_deadline": expired_time
        },
        "confirmed": True
    }
    
    res = session.post(f"{BASE_URL}/spot/manual/execute", json=trade)
    if res.status_code >= 400 and "expired" in res.text.lower():
         log("Expired Proposal Rejected", "PASS")
    else:
         log(f"Expired Proposal NOT Rejected: {res.status_code} {res.text}", "FAIL")

try:
    login()
    test_stop()
    test_undo()
    test_idempotency()
    test_ttl()
except Exception as e:
    log(f"Script Error: {e}", "FAIL")
