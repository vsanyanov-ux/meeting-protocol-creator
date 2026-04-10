import os
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

langfuse = Langfuse(
    public_key=public_key,
    secret_key=secret_key,
    host=host
)

print(f"Langfuse object: {langfuse}")
print(f"Available methods: {[m for m in dir(langfuse) if not m.startswith('_')]}")

import inspect
sig = inspect.signature(langfuse.start_observation)
print(f"Signature of start_observation: {sig}")

try:
    # Let's try to see if 'trace' is a separate method now or if it's 'start_trace'
    trace_methods = [m for m in dir(langfuse) if 'trace' in m.lower()]
    print(f"Trace-related methods: {trace_methods}")

    # Trying common v4 pattern: start_observation with lowercase 'name' and maybe positional or different args
    # Actually, maybe it's trace(...) but it's not in dir()?
    # No, we already tried trace().
    
    # Try creating observation without 'type'
    obs = langfuse.start_observation(name="test_obs")
    print(f"Observation created: {obs.id}")
except Exception as e:
    print(f"Error: {e}")
