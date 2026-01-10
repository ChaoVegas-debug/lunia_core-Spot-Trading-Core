import requests
import sys

BASE_URL = "http://localhost:8080"

def seed():
    # 1. Login
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "trader@example.com",
            "password": "trader123"
        })
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        return

    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Seed Limits
    limits = [
        {"scope": "SYSTEM", "subject": "*", "key": "max_positions", "value": "5"},
        {"scope": "SYSTEM", "subject": "*", "key": "max_symbol_exposure_pct", "value": "0.2"},
        {"scope": "SYSTEM", "subject": "*", "key": "max_daily_loss_pct", "value": "0.05"}
    ]

    for l in limits:
        r = requests.post(f"{BASE_URL}/admin/limits", json=l, headers=headers)
        print(f"Seeding {l['key']}: {r.status_code}")

if __name__ == "__main__":
    seed()
