import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"
PASSWORD = os.getenv("APP_PASSWORD", "protocolist2026")

def test_auth():
    print(f"Testing auth with password: {PASSWORD}")
    
    # 1. Test public endpoint (health)
    print("\n1. Testing public endpoint (/health)...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    
    # 2. Test protected endpoint without password
    print("\n2. Testing protected endpoint (/info) without password...")
    resp = requests.get(f"{BASE_URL}/info")
    print(f"Status: {resp.status_code}")
    if resp.status_code == 401:
        print("✅ Correctly rejected without password")
    else:
        print("❌ Should have been rejected")

    # 3. Test protected endpoint with WRONG password
    print("\n3. Testing protected endpoint (/info) with WRONG password...")
    resp = requests.get(f"{BASE_URL}/info", headers={"X-App-Password": "wrong"})
    print(f"Status: {resp.status_code}")
    if resp.status_code == 401:
        print("✅ Correctly rejected with wrong password")
    else:
        print("❌ Should have been rejected")

    # 4. Test protected endpoint with CORRECT password
    print("\n4. Testing protected endpoint (/info) with CORRECT password...")
    resp = requests.get(f"{BASE_URL}/info", headers={"X-App-Password": PASSWORD})
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        print("✅ Correctly accepted with password")
    else:
        print(f"❌ Failed to accept correct password: {resp.text}")

    # 5. Test download endpoint with query param
    print("\n5. Testing /download with query param password...")
    # Using a fake file ID just to check auth
    resp = requests.get(f"{BASE_URL}/download/fake-id?password={PASSWORD}")
    print(f"Status: {resp.status_code}")
    if resp.status_code == 404:
        print("✅ Auth passed (got 404 for non-existent file, not 401)")
    elif resp.status_code == 401:
        print("❌ Query param auth failed")
    else:
        print(f"Status: {resp.status_code}")

if __name__ == "__main__":
    try:
        test_auth()
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure the backend is running on http://localhost:8000")
