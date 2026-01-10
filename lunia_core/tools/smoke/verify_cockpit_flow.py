import requests
import json
import sys
import os
import time

# Configuration
BASE_URL = "http://127.0.0.1:5000"
TRADER_EMAIL = "trader@example.com"
TRADER_PASSWORD = "trader123"
REPORT_PATH = "reports/SMOKE_VERIFY_REPORT.md"

def log(msg):
    print(f"[SMOKE] {msg}")

def run_smoke_test():
    log("Starting Smoke Test Sequence...")
    
    report_lines = ["# Smoke Verification Report", f"Date: {time.ctime()}", "", "| Check | Status | Details |", "|---|---|---|"]
    
    session = requests.Session()
    
    # 1. Authentication
    try:
        resp = session.post(f"{BASE_URL}/auth/login", json={"email": TRADER_EMAIL, "password": TRADER_PASSWORD})
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            session.headers.update({"Authorization": f"Bearer {token}"})
            report_lines.append("| Auth | PASS | Login successful |")
            log("Auth: PASS")
        else:
            report_lines.append(f"| Auth | FAIL | Login failed: {resp.status_code} |")
            log(f"Auth: FAIL {resp.status_code}")
            return False
    except Exception as e:
        report_lines.append(f"| Auth | FAIL | Connection error: {e} |")
        log(f"Auth: FAIL {e}")
        return False

    # 2. Ops State Read
    try:
        resp = session.get(f"{BASE_URL}/ops/state")
        if resp.status_code == 200:
            state = resp.json()
            report_lines.append("| Ops State | PASS | Read success |")
        else:
            report_lines.append(f"| Ops State | FAIL | {resp.status_code} |")
    except Exception as e:
        report_lines.append(f"| Ops State | FAIL | {e} |")

    # 3. Portfolio Structure
    try:
        resp = session.get(f"{BASE_URL}/portfolio/structure")
        if resp.status_code == 200:
            data = resp.json()
            portfolios = data.get("portfolios", [])
            count = len(portfolios)
            if count >= 2:
                report_lines.append(f"| Portfolios | PASS | Found {count} portfolios |")
            else:
                report_lines.append(f"| Portfolios | WARN | Found {count} portfolios (Expected >= 2 via Seed) |")
        else:
             report_lines.append(f"| Portfolios | FAIL | {resp.status_code} |")
    except Exception as e:
        report_lines.append(f"| Portfolios | FAIL | {e} |")

    # 4. Risk Limits (Admin Read check - might fail if Trader doesn't have partial access, but in our app Trader CAN read limits via getRisk combined?)
    # Usually limits read is open or needs specific endpoint.
    # Risk Widget calls GET /admin/limits? No, it calls /spot/risk and /admin/limits.
    # Let's check /spot/risk first.
    try:
        resp = session.get(f"{BASE_URL}/spot/risk")
        if resp.status_code == 200:
            report_lines.append("| Risk Config | PASS | Read success |")
        else:
            report_lines.append(f"| Risk Config | FAIL | {resp.status_code} |")
    except Exception as e:
        report_lines.append(f"| Risk Config | FAIL | {e} |")

    # 5. Logs Access
    try:
        resp = session.get(f"{BASE_URL}/ops/logs")
        if resp.status_code == 200:
             report_lines.append("| Logs | PASS | Read success |")
        else:
             report_lines.append(f"| Logs | FAIL | {resp.status_code} |")
    except Exception as e:
        report_lines.append(f"| Logs | FAIL | {e} |")

    # 6. Capital Write (Safe Test)
    try:
        # We read first to restore later or just toggle slightly?
        # Let's just confirm endpoint answers 400 on bad data or 200 on valid.
        resp = session.post(f"{BASE_URL}/ops/capital", json={"cap_pct": 0.5})
        if resp.status_code == 200:
            report_lines.append("| Capital Write | PASS | Update success |")
        else:
            report_lines.append(f"| Capital Write | FAIL | {resp.status_code} |")
    except Exception as e:
        report_lines.append(f"| Capital Write | FAIL | {e} |")

    # Write Report
    os.makedirs("reports", exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write("\n".join(report_lines))
    
    log(f"Smoke Test Complete. Report at {REPORT_PATH}")
    return True

if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
