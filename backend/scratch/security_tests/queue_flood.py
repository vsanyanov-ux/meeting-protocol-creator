import requests
import concurrent.futures
import os

BASE_URL = "http://localhost:8000"

def start_task(i):
    audio_file = "_Совещания/test_meeting_30s.mp4"
    if not os.path.exists(audio_file):
        return "File not found"
        
    try:
        with open(audio_file, "rb") as f:
            files = {"file": (f"flood_{i}.mp4", f, "video/mp4")}
            resp = requests.post(f"{BASE_URL}/process-meeting", files=files, data={
                "session_id": f"flood-test-{i}",
                "send_email": "false"
            })
        return resp.status_code
    except Exception as e:
        return str(e)

def test_flood():
    print("--- TESTING QUEUE FLOOD (MAX=5) ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(start_task, range(15)))
    
    success = results.count(200)
    rejected = results.count(503)
    
    print(f"Success (200): {success}")
    print(f"Rejected (503): {rejected}")

if __name__ == "__main__":
    test_flood()
