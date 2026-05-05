import requests
import os

BASE_URL = "http://localhost:8000"

def test_path_traversal():
    print("Starting Path Traversal attack simulation...")
    
    # 1. Attempt to use a relative path in existing_file_id
    print("\n[1] Testing existing_file_id traversal...")
    # Assume status.db exists in storage/
    traversal_id = "../storage/status" 
    data = {
        "existing_file_id": traversal_id,
        "session_id": "traversal-test"
    }
    response = requests.post(f"{BASE_URL}/process-meeting", data=data)
    print(f"Response: {response.status_code} - {response.text}")
    
    # 2. Attempt to use a malicious extension
    print("\n[2] Testing extension manipulation during upload...")
    malicious_filename = "test.py"
    with open("malicious.txt", "w") as f:
        f.write("print('hacked')")
        
    try:
        with open("malicious.txt", "rb") as f:
            files = {"file": ("../../main.py", f, "text/plain")} # Trying to overwrite main.py
            response = requests.post(f"{BASE_URL}/process-meeting", files=files)
            print(f"Response: {response.status_code} - {response.text}")
    finally:
        if os.path.exists("malicious.txt"):
            os.remove("malicious.txt")

    # 3. Attempt to read sensitive files via status endpoint if ID is reflected
    print("\n[3] Testing status ID reflection...")
    # This is less likely to work but worth checking
    vuln_id = "../../../etc/passwd"
    response = requests.get(f"{BASE_URL}/status/{vuln_id}")
    print(f"Response status: {response.status_code}")

if __name__ == "__main__":
    test_path_traversal()
