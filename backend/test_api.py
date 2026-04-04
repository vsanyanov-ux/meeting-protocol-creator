import requests
import time
import sys
import os

API_URL = "http://localhost:8000"

def test_pipeline(file_path):
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    print(f"--- Starting test for {file_path} ---")
    
    # 1. Upload
    try:
        with open(file_path, "rb") as f:
            files = {"file": f}
            response = requests.post(f"{API_URL}/process-meeting", files=files)
        
        if response.status_code != 200:
            print(f"Upload failed: {response.status_code} - {response.text}")
            return
        
        data = response.json()
        file_id = data["file_id"]
        print(f"File uploaded! ID: {file_id}")
        
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the backend. Is it running on port 8000?")
        return

    # 2. Poll Status
    last_message = ""
    while True:
        try:
            status_response = requests.get(f"{API_URL}/status/{file_id}")
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data["status"]
                message = status_data["message"]
                
                if message != last_message:
                    print(f"[{status.upper()}] {message}")
                    last_message = message
                
                if status == "completed":
                    print("\n--- Success! Check your email. ---")
                    break
                if status == "error":
                    print(f"\n--- Failed: {message} ---")
                    break
            else:
                print(f"Status check failed: {status_response.status_code}")
                break
        except Exception as e:
            print(f"Error polling: {e}")
            break
            
        time.sleep(5)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <path_to_audio_file>")
    else:
        test_pipeline(sys.argv[1])
