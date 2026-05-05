import requests
import os
import uuid
import time

BASE_URL = "http://localhost:8000"
FILE_SIZE_MB = 10  # Smaller for testing, but many of them
COUNT = 50

def simulate_disk_fill():
    print(f"Starting Disk Fill attack simulation with {COUNT} files of {FILE_SIZE_MB}MB each...")
    
    # Create a dummy large file
    dummy_file = "large_dummy.bin"
    with open(dummy_file, "wb") as f:
        f.write(os.urandom(FILE_SIZE_MB * 1024 * 1024))
    
    success_count = 0
    try:
        for i in range(COUNT):
            file_id = str(uuid.uuid4())
            with open(dummy_file, "rb") as f:
                files = {"file": (f"attack_{i}.bin", f, "application/octet-stream")}
                data = {"session_id": "attack-session"}
                response = requests.post(f"{BASE_URL}/process-meeting", files=files, data=data)
                
                if response.status_code == 200:
                    success_count += 1
                    print(f"[{i+1}/{COUNT}] Upload success: {response.json().get('file_id')}")
                else:
                    print(f"[{i+1}/{COUNT}] Upload failed: {response.status_code} - {response.text}")
                    if response.status_code == 500:
                        print("CRITICAL: Server returned 500. Disk might be full or process crashed.")
                        break
            time.sleep(0.1)
    finally:
        if os.path.exists(dummy_file):
            os.remove(dummy_file)
            
    print(f"\nAttack finished. Total successful uploads: {success_count}")
    print(f"Check the 'uploads' directory size!")

if __name__ == "__main__":
    simulate_disk_fill()
