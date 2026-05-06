import os
import langfuse
from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv("backend/.env")

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

# Try module level trace
try:
    t = langfuse.trace(name="test")
    print("Module level langfuse.trace works")
except Exception as e:
    print(f"Module level langfuse.trace failed: {e}")

# Try client instance trace
client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
try:
    t = client.trace(name="test")
    print("Client instance client.trace works")
except Exception as e:
    print(f"Client instance client.trace failed: {e}")
