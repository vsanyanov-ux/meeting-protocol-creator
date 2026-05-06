import os
from langfuse import Langfuse
from dotenv import load_dotenv

load_dotenv("backend/.env")

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST") or "https://cloud.langfuse.com"

client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

span = client.start_span(name="test_root")
print(f"Span object methods: {[m for m in dir(span) if not m.startswith('_')]}")

gen = span.start_generation(name="test_gen")
print(f"Generation object methods: {[m for m in dir(gen) if not m.startswith('_')]}")
