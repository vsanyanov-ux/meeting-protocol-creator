import os
from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv("backend/.env")

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

span = client.start_span(name="test_root")
try:
    gen = span.start_observation(
        name="test_gen",
        as_type="generation",
        model="gpt-3.5-turbo"
    )
    gen.update(usage={"input": 10, "output": 20})
    print("gen.update with usage worked")
    gen.end()
except Exception as e:
    print(f"gen.update with usage failed: {e}")

client.flush()
