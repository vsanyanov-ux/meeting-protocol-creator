import os
import uuid
import time
from langfuse import Langfuse

# Use real keys if available in env, or dummy ones
pk = os.getenv("LANGFUSE_PUBLIC_KEY", "pk-mock")
sk = os.getenv("LANGFUSE_SECRET_KEY", "sk-mock")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

print("--- Testing WITH is_langfuse_span ---")
from langfuse.span_filter import is_langfuse_span

lf_filtered = Langfuse(
    public_key=pk, 
    secret_key=sk, 
    host=host,
    should_export_span=is_langfuse_span
)

trace_id = uuid.uuid4().hex
trace = lf_filtered.trace(id=trace_id, name="filtered_trace")
span = trace.span(name="manual_span")
print(f"Manual span ID: {span.id}")
# Check if internal spans list has things
# Note: Langfuse SDK is async and uses a queue.

print("--- Testing WITHOUT is_langfuse_span ---")
lf_unfiltered = Langfuse(
    public_key=pk, 
    secret_key=sk, 
    host=host
)
trace2 = lf_unfiltered.trace(id=uuid.uuid4().hex, name="unfiltered_trace")
span2 = trace2.span(name="manual_span_unfiltered")
print(f"Manual span 2 ID: {span2.id}")

lf_filtered.flush()
lf_unfiltered.flush()
print("Flushed. If this script hangs, it might be due to SDK background threads.")
