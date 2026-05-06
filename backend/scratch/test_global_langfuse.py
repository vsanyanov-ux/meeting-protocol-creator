import os
import langfuse
from dotenv import load_dotenv

load_dotenv("backend/.env")

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

# Try global initialization
try:
    langfuse.configure(public_key=public_key, secret_key=secret_key, host=host)
    print("langfuse.configure worked")
    t = langfuse.trace(name="test_global")
    print("langfuse.trace after configure worked")
except Exception as e:
    print(f"Global langfuse.trace failed: {e}")
