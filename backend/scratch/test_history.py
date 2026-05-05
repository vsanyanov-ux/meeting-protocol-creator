import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"
PASSWORD = os.getenv("APP_PASSWORD")

def test_history():
    print("Testing /history endpoint...")
    headers = {"X-App-Password": PASSWORD}
    
    # 1. Test unauthorized
    resp = requests.get(f"{BASE_URL}/history")
    if resp.status_code == 401:
        print("[OK] Unauthorized access blocked correctly.")
    else:
        print(f"[FAIL] Unauthorized access test failed (Status: {resp.status_code})")

    # 2. Test authorized
    resp = requests.get(f"{BASE_URL}/history", headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        print(f"[OK] Authorized access success. Found {len(data)} items in history.")
        for item in data[:3]:
            print(f"   - {item['filename']} ({item['updated_at']}) - Exists: {item['file_exists']}")
    else:
        print(f"[FAIL] Authorized access test failed (Status: {resp.status_code}, Detail: {resp.text})")

if __name__ == "__main__":
    try:
        test_history()
    except Exception as e:
        print(f"[ERROR] Error: {e}")

