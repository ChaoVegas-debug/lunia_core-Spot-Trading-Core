
import requests
import json
import sys

BASE_URL = "http://localhost:8080"
HEADERS = {
    "X-Admin-Token": "dev-ops-token",
    "Content-Type": "application/json"
}

def test_endpoint(name, path):
    print(f"Testing {name} ({path})...", end=" ")
    try:
        resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            # Basic validation
            if path == "/fund/overview" and "total_aum" in data:
                print("PASS")
                return True
            elif path == "/fund/portfolio" and "by_asset" in data:
                print("PASS")
                return True
            elif path == "/fund/strategies" and isinstance(data, list):
                print("PASS")
                return True
            elif path == "/fund/risk" and "max_drawdown_pct" in data:
                print("PASS")
                return True
            elif path == "/fund/accounts" and isinstance(data, list):
                print("PASS")
                return True
            else:
                print(f"FAIL (Unexpected Struct: {data.keys() if isinstance(data, dict) else type(data)})")
                return False
        else:
            print(f"FAIL (Status {resp.status_code})")
            print(resp.text)
            return False
    except Exception as e:
        print(f"FAIL (Exception: {e})")
        return False

def run_tests():
    print(f"--- Verifying Fund Panel API ({BASE_URL}) ---")
    
    tests = [
        ("Fund Overview", "/fund/overview"),
        ("Fund Portfolio", "/fund/portfolio"),
        ("Fund Strategies", "/fund/strategies"),
        ("Fund Risk", "/fund/risk"),
        ("Fund Accounts", "/fund/accounts"),
    ]
    
    passed = 0
    for name, path in tests:
        if test_endpoint(name, path):
            passed += 1
            
    print(f"--- Result: {passed}/{len(tests)} Passed ---")
    if passed == len(tests):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
