import os
from dotenv import load_dotenv
from langfuse import Langfuse
import uuid

load_dotenv()

def test_trace_object():
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    lf = Langfuse(public_key=pk, secret_key=sk)
    
    trace_id = uuid.uuid4().hex
    session_id = f"trace-obj-session-{uuid.uuid4().hex[:8]}"
    
    print(f"Testing lf.trace() with ID {trace_id} and session {session_id}")
    
    try:
        # В SDK v4.0.6 метод trace() создает объект, но не обязательно отправляет его сразу.
        trace = lf.trace(
            id=trace_id,
            session_id=session_id,
            user_id="trace-obj-user",
            name="trace_object_test"
        )
        
        # Теперь попробуем создать наблюдение внутри этого трейса
        span = trace.span(name="child_span")
        span.end(output="success")
        
        lf.flush()
        print("Trace object test completed. Check dashboard.")
    except Exception as e:
        print(f"lf.trace() failed: {e}")

if __name__ == "__main__":
    test_trace_object()
