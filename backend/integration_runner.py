import requests
import json
import time
import sys
import os

# Set sys.stdout and sys.stderr to UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_pipeline(file_path):
    url = "http://127.0.0.1:8000/process-meeting"
    
    if not os.path.exists(file_path):
        print(f"Error: File not found.")
        return

    print(f"--- Starting test... ---")
    
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        response = requests.post(url, files=files)
    
    if response.status_code != 200:
        print(f"FAILED to upload: {response.status_code} - {response.text}")
        return
    
    data = response.json()
    file_id = data.get("file_id")
    print(f"File uploaded! ID: {file_id}")
    
    # Poll for status
    status_url = f"http://127.0.0.1:8000/status/{file_id}"
    while True:
        res = requests.get(status_url)
        if res.status_code == 200:
            status_data = res.json()
            status = status_data.get("status")
            # Filter out non-ASCII characters from the message to avoid charmap errors
            message = "".join([c if ord(c) < 128 else "?" for c in status_data.get("message", "")])
            
            print(f"[{status.upper()}] {message}")
            
            if status == "completed":
                print("\n--- Success! ---")
                break
            elif status == "error":
                print(f"\n--- FAILED: {message} ---")
                break
        else:
            print(f"Error checking status: {res.text}")
            break
        
        time.sleep(3)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_api.py <path_to_audio>")
    else:
        test_pipeline(sys.argv[1])
