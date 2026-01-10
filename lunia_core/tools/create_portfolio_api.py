import requests
import json
import time

BASE_URL = "http://localhost:8080"
HEADERS = {
    "X-Admin-Token": "local-dev-token",
    "Content-Type": "application/json"
}

def create_portfolio():
    print("Step 1: Setting Config...")
    config_payload = {
        "risk_profile": "BALANCED",
        "horizon": "LONG_TERM",
        "investment_amount": 10000.0,
        "base_currency": "USDT"
    }
    resp = requests.post(f"{BASE_URL}/api/portfolios/draft/config", json=config_payload, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Failed Config: {resp.text}")
        return
    print("Config OK.")

    print("Step 2: Setting Assets...")
    assets_payload = {"assets": ["BTC", "ETH", "SOL", "AVAX"]}
    resp = requests.post(f"{BASE_URL}/api/portfolios/draft/assets", json=assets_payload, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Failed Assets: {resp.text}")
        return
    print("Assets OK.")

    print("Step 3: Creating Portfolio...")
    resp = requests.post(f"{BASE_URL}/api/portfolios/create", json={}, headers=HEADERS)
    if resp.status_code != 200:
        print(f"Failed Create: {resp.text}")
        return
    
    data = resp.json()
    print(f"Portfolio Created! ID: {data.get('id')}")

if __name__ == "__main__":
    try:
        create_portfolio()
    except Exception as e:
        print(f"Error: {e}")
