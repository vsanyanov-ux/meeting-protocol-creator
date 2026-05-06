import os
from langfuse import Langfuse
import inspect
from dotenv import load_dotenv

load_dotenv("backend/.env")

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

span = client.start_span(name="test_root")
print(f"span.update_trace signature: {inspect.signature(span.update_trace)}")
