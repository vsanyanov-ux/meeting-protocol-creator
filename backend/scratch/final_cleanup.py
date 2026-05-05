import os
import httpx
import time
from dotenv import load_dotenv

load_dotenv()

pk = os.getenv("LANGFUSE_PUBLIC_KEY")
sk = os.getenv("LANGFUSE_SECRET_KEY")
host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").rstrip('/')

def final_cleanup():
    url = f"{host}/api/public/traces"
    print(f"Final cleanup of non-protocolist traces...")
    
    try:
        response = httpx.get(
            url,
            auth=(pk, sk),
            params={"limit": 100},
            timeout=60.0
        )
        if response.status_code != 200:
            print(f"Error: {response.text}")
            return
            
        data = response.json()
        traces = data.get("data", [])
        
        deleted = 0
        for t in traces:
            name = t.get("name")
            if name != "protocolist":
                t_id = t.get("id")
                print(f"Deleting {t_id} (Name: {name})... ", end="")
                del_resp = httpx.delete(f"{url}/{t_id}", auth=(pk, sk), timeout=30.0)
                if del_resp.status_code in [200, 204]:
                    print("OK")
                    deleted += 1
                else:
                    print(f"FAIL ({del_resp.status_code})")
                time.sleep(1) # Be patient
                
        print(f"Deleted {deleted} traces in this pass.")
    except Exception as e:
        print(f"Cleanup failed: {e}")

if __name__ == "__main__":
    final_cleanup()
