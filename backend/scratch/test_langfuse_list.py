import os
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

pk = os.getenv("LANGFUSE_PUBLIC_KEY")
sk = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL")

print(f"Connecting to {host}...")
lf = Langfuse(public_key=pk, secret_key=sk, host=host)

try:
    # Try to list traces
    # Based on latest SDK docs, it might be via the client
    traces = lf.get_traces(limit=50)
    print(f"Found {len(traces.data)} traces in the first batch.")
    
    for trace in traces.data:
        print(f"ID: {trace.id}, Name: {trace.name}")
        
except Exception as e:
    print(f"Error: {e}")
    # Fallback to alternative method if needed
