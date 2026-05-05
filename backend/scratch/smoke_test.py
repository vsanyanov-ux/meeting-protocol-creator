import requests
import time
import os
import sys
import io

# Force UTF-8 for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://localhost:8000"

def smoke_test():
    audio_file = "_Совещания/test_meeting_30s.mp4"
    if not os.path.exists(audio_file):
        print(f"Error: {audio_file} not found.")
        return

    print(f"--- SMOKE TEST: Uploading {audio_file} ---")
    try:
        with open(audio_file, "rb") as f:
            files = {"file": (os.path.basename(audio_file), f, "video/mp4")}
            response = requests.post(f"{BASE_URL}/process-meeting", files=files)
            
        if response.status_code != 200:
            print(f"Upload failed: {response.status_code} - {response.text}")
            return
            
        file_id = response.json().get("file_id")
        print(f"Processing started. File ID: {file_id}")
        
        start_time = time.time()
        while time.time() - start_time < 300: # 5 mins timeout
            status_resp = requests.get(f"{BASE_URL}/status/{file_id}")
            data = status_resp.json()
            status = data.get("status")
            msg = data.get("message")
            print(f"[{int(time.time() - start_time)}s] Status: {status} - {msg}")
            
            if status == "completed":
                print("\nSUCCESS: Protocol generated!")
                return
            elif status == "error":
                print(f"FAILURE: {msg}")
                return
                
            time.sleep(10)
            
        print("TIMEOUT: Processing took too long.")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    smoke_test()
