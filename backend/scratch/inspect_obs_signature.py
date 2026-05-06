import os
from langfuse import Langfuse
import inspect
from dotenv import load_dotenv

load_dotenv("backend/.env")

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

print(f"client.start_observation signature: {inspect.signature(client.start_observation)}")
