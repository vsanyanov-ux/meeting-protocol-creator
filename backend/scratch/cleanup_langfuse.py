import os
import httpx
import time
from dotenv import load_dotenv

load_dotenv()

pk = os.getenv("LANGFUSE_PUBLIC_KEY")
sk = os.getenv("LANGFUSE_SECRET_KEY")
host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").rstrip('/')

def delete_with_retry(client, url, trace_id, retries=2):
    for i in range(retries):
        try:
            resp = client.delete(
                f"{url}/{trace_id}",
                auth=(pk, sk),
                timeout=30.0
            )
            if resp.status_code in [200, 204]:
                return "deleted"
            elif resp.status_code == 429:
                wait = (i + 1) * 10
                print(f"Rate limited (429). Waiting {wait}s...")
                time.sleep(wait)
            elif resp.status_code == 404:
                return "not_found"
            else:
                print(f"Failed to delete {trace_id}: {resp.status_code} - {resp.text}")
                return "error"
        except Exception as e:
            print(f"Error deleting {trace_id}: {e}")
            time.sleep(2)
    return "timeout/fail"

def cleanup_traces():
    url = f"{host}/api/public/traces"
    print(f"Starting cleanup at {host}...")
    
    ids_to_delete = []
    page = 1
    
    while True:
        print(f"Scanning page {page}...")
        try:
            response = httpx.get(
                url,
                auth=(pk, sk),
                params={"page": page, "limit": 100},
                timeout=60.0
            )
            if response.status_code != 200:
                print(f"Error scanning: {response.text}")
                break
            data = response.json()
            traces = data.get("data", [])
            if not traces: break
            for t in traces:
                if t.get("name") != "protocolist":
                    ids_to_delete.append((t.get("id"), t.get("name")))
            if page >= data.get("meta", {}).get("totalPages", 1): break
            page += 1
        except Exception as e:
            print(f"Scan failed: {e}")
            break

    total = len(ids_to_delete)
    print(f"Found {total} traces to delete.")
    
    deleted_count = 0
    with httpx.Client() as client:
        for i, (trace_id, trace_name) in enumerate(ids_to_delete):
            print(f"[{i+1}/{total}] {trace_id} ({trace_name})... ", end="", flush=True)
            res = delete_with_retry(client, url, trace_id)
            print(res)
            if res == "deleted":
                deleted_count += 1
            
            # Very slow delay to avoid 429
            time.sleep(2.0)

    print(f"\nCleanup complete! Deleted {deleted_count} traces.")

if __name__ == "__main__":
    cleanup_traces()
