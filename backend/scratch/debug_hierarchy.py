from langfuse import Langfuse
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

def debug_hierarchy():
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")
    
    lf = Langfuse(public_key=pk, secret_key=sk, host=host)
    trace_id = uuid.uuid4().hex
    
    # 1. Create root span
    root = lf.start_observation(
        name="root_span_test",
        as_type="span",
        trace_context={"trace_id": trace_id}
    )
    print(f"Root observation ID: {root.id}, Trace ID: {root.trace_id}")
    
    # 2. Create child generation
    child = root.start_observation(
        name="child_gen_test",
        as_type="generation"
    )
    print(f"Child observation ID: {child.id}, Trace ID: {child.trace_id}")
    
    child.end()
    root.end()
    lf.flush()
    print("Flushed. Check dashboard for 'root_span_test' trace with 'child_gen_test' inside.")

if __name__ == "__main__":
    debug_hierarchy()
