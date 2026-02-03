
import json
import os
import sys
from pathlib import Path

# ABSOLUTE TRUTH KEYS (From Step 2141)
API_KEY = "ckPpwSL8I7dnUTJcwUDEcVIXzKbrVOTqHmv7TLYTG8qY3vSV3HsMcJvEE52IEN9v"
SECRET_KEY = "IuPnzSGcia743emsE06kx5MspuZcFybPaVwxTceYJCmOd9aRnAYFBSwBrClUsyDI"

SECRETS_PATH = Path("/Users/neomind/alladin/lunia_core-Spot-Trading-Core/.secrets.json")

def enforce_keys():
    print("--- COMBAT MODE KEY INJECTION ---")
    
    # 1. Cleanse Keys
    clean_key = API_KEY.strip()
    clean_secret = SECRET_KEY.strip()
    
    if len(clean_key) != 64:
        print(f"WARNING: Key length {len(clean_key)} != 64")
    if len(clean_secret) != 64:
        print(f"WARNING: Secret length {len(clean_secret)} != 64")

    # 2. Construct Payload
    payload = {
        "binance": {
            "api_key": clean_key,
            "api_secret": clean_secret,
            "is_testnet": False # FORCE MAINNET
        }
    }
    
    # 3. Write Atomic
    print(f"Writing to {SECRETS_PATH}...")
    SECRETS_PATH.write_text(json.dumps(payload, indent=2))
    print("SUCCESS: Keys written to disk.")
    
    # 4. Verify Readback
    readback = json.loads(SECRETS_PATH.read_text())
    rb_key = readback["binance"]["api_key"]
    if rb_key == clean_key:
        print("VERIFIED: Disk content matches memory.")
    else:
        print("FAILURE: Readback mismatch!")
        sys.exit(1)

if __name__ == "__main__":
    enforce_keys()
