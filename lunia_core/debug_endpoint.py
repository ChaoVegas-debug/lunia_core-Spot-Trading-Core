import requests
import sys

BASE_URL = "http://localhost:8080"

def test():
    # 1. Login
    print(f"Logging in to {BASE_URL}...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={
            "email": "trader@example.com",
            "password": "trader123"
        })
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code} {resp.text}")
        return

    token = resp.json()["access_token"]
    print(f"Got token: {token[:10]}...")

    # 2. Get Limits
    print("Fetching /admin/limits...")
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/admin/limits", headers=headers)
    
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")

if __name__ == "__main__":
    test()
