import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

pk = os.getenv("LANGFUSE_PUBLIC_KEY")
sk = os.getenv("LANGFUSE_SECRET_KEY")
host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").rstrip('/')

def list_traces():
    url = f"{host}/api/public/traces"
    print(f"Calling API: {url}")
    
    try:
        response = httpx.get(
            url,
            auth=(pk, sk),
            params={"limit": 100},
            timeout=60.0
        )
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return
            
        data = response.json()
        traces = data.get("data", [])
        
        print(f"Found {len(traces)} traces.")
        
        # Count names
        names = {}
        for t in traces:
            name = t.get("name") or "None"
            names[name] = names.get(name, 0) + 1
            
        print("\nTrace name distribution:")
        for name, count in names.items():
            print(f"- {name}: {count}")
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    list_traces()
