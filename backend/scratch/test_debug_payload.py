import os
from dotenv import load_dotenv
from langfuse import Langfuse, propagate_attributes
import uuid
import time
import logging

# Enable debug logging for Langfuse
logging.basicConfig(level=logging.DEBUG)
load_dotenv()

def test_debug_payload():
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    lf = Langfuse(public_key=pk, secret_key=sk, debug=True)
    
    session_id = f"debug-session-{uuid.uuid4().hex[:8]}"
    trace_id = uuid.uuid4().hex
    
    print(f"Testing debug payload for session {session_id}")
    
    with propagate_attributes(session_id=session_id, user_id="debug-user"):
        with lf.start_as_current_observation(
            name="debug_root",
            trace_context={"trace_id": trace_id}
        ) as root:
            root.update(metadata={"foo": "bar"})
            
            # Start a child
            child = lf.start_observation(name="debug_child")
            child.end()
            
    lf.flush()
    print("Check logs for payloads.")

if __name__ == "__main__":
    test_debug_payload()
