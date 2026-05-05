import requests
import concurrent.futures
import time
import uuid

BASE_URL = "http://localhost:8000"

def hammer_status(file_id):
    for _ in range(50):
        try:
            resp = requests.get(f"{BASE_URL}/status/{file_id}")
            if resp.status_code != 200:
                print(f"Error status: {resp.status_code}")
        except Exception as e:
            print(f"Request failed: {e}")

def start_task():
    try:
        resp = requests.post(f"{BASE_URL}/process-meeting", data={
            "session_id": "race-test",
            "send_email": "false"
        })
        if resp.status_code == 200:
            return resp.json().get("file_id")
    except Exception as e:
        print(f"Post failed: {e}")
    return None

def test_race():
    print("--- TESTING SQLITE RACE ---")
    file_ids = []
    for _ in range(5):
        fid = start_task()
        if fid: file_ids.append(fid)
    
    if not file_ids:
        print("Failed to start tasks.")
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for fid in file_ids:
            futures.append(executor.submit(hammer_status, fid))
        
        # Also try to create new tasks while hammering
        for _ in range(10):
            futures.append(executor.submit(start_task))
            time.sleep(0.1)
            
        concurrent.futures.wait(futures)
    
    print("Race test complete. Check server logs for 'database is locked'.")

if __name__ == "__main__":
    test_race()
