import os
import uuid
import datetime
from langfuse import Langfuse
from loguru import logger

# Mock credentials (or use env if present)
pk = os.getenv("LANGFUSE_PUBLIC_KEY")
sk = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

if not pk or not sk:
    print("SKIP: Missing Langfuse keys")
    exit(0)

lf = Langfuse(public_key=pk, secret_key=sk, host=host)

trace_id = uuid.uuid4().hex
print(f"Testing Trace ID: {trace_id}")

try:
    # 1. Create trace
    trace = lf.trace(
        id=trace_id,
        name="test_trace_name",
        metadata={"test": True}
    )
    print(f"Trace created: {trace.id}")

    # 2. Create span
    span = trace.span(
        name="test_span_name",
        input={"test_input": 123}
    )
    print(f"Span created: {span.id}")
    
    # 3. Create generation
    gen = span.start_observation(
        name="test_gen",
        as_type="generation",
        model="test-model"
    )
    print(f"Generation created: {gen.id}")
    gen.end(output="test output")

    span.end(output={"success": True})
    
    # 4. Update trace
    trace.update(output="Finished test")
    
    lf.flush()
    print("SUCCESS: All calls completed")

except Exception as e:
    print(f"FAILURE: {e}")
    import traceback
    traceback.print_exc()
