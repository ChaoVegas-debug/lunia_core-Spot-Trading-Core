import os
import json
import hashlib
from pathlib import Path

def get_hash(s):
    if not s: return "EMPTY"
    return hashlib.sha256(s.encode()).hexdigest()[:8]

def diagnose():
    print(f"CWD: {os.getcwd()}")
    
    # 1. Check ENV
    env_key = os.getenv("BINANCE_API_KEY", "")
    env_secret = os.getenv("BINANCE_API_SECRET", "")
    print(f"ENV: KeyLen={len(env_key)} Hash={get_hash(env_key)}")
    print(f"ENV: SecretLen={len(env_secret)} Hash={get_hash(env_secret)}")
    
    # 2. Check File (Relative to CWD)
    p = Path(os.getcwd()) / ".secrets.json"
    print(f"Checking Path: {p.absolute()}")
    if p.exists():
        try:
            with open(p, "r") as f:
                data = json.load(f)
                b = data.get("binance", {})
                k = b.get("api_key", "")
                s = b.get("api_secret", "")
                print(f"FILE: KeyLen={len(k)} Hash={get_hash(k)}")
                print(f"FILE: SecretLen={len(s)} Hash={get_hash(s)}")
        except Exception as e:
            print(f"FILE READ ERROR: {e}")
    else:
        print("FILE: Not found at this path")

if __name__ == "__main__":
    diagnose()
