import os
from dotenv import load_dotenv
from langfuse_client import PipelineTrace
import uuid
import time

load_dotenv()

def test_final_fix():
    file_id = str(uuid.uuid4())
    session_id = f"final-fix-session-{uuid.uuid4().hex[:8]}"
    
    print(f"Testing FINAL FIX with session {session_id} and trace {file_id}")
    
    with PipelineTrace(
        file_id=file_id,
        filename="final_test.mp3",
        provider="yandex",
        metadata={"email": "v.sanyanov@gmail.com"},
        session_id=session_id
    ) as trace:
        
        # Start a span
        span = trace.start_span("normalization")
        time.sleep(0.5)
        
        # Log a generation
        trace.log_generation(
            input_messages=[{"role": "user", "content": "Hello"}],
            output_text="Final fix is here!",
            model="gpt-4",
            latency_ms=500,
            input_tokens=10,
            output_tokens=20,
            name="Create Protocol"
        )
        
        # End span
        trace.end_span("normalization", {"status": "ok"})
        
    print("Done. Trace ID:", file_id.replace("-", ""))

if __name__ == "__main__":
    test_final_fix()
