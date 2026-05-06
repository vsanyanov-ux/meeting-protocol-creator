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
gen = span.start_observation(name="test_gen", as_type="generation")
print(f"gen.update signature: {inspect.signature(gen.update)}")
