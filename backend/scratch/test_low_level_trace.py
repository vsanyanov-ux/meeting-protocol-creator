import os
from dotenv import load_dotenv
from langfuse import Langfuse
import uuid
import datetime

load_dotenv()

def test_low_level_trace():
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    lf = Langfuse(public_key=pk, secret_key=sk)
    
    trace_id = uuid.uuid4().hex
    session_id = f"low-level-session-{uuid.uuid4().hex[:8]}"
    
    print(f"Testing low-level trace {trace_id} with session {session_id}")
    
    try:
        # Use the ingestion API directly
        res = lf.api.ingestion.batch(
            batch=[
                {
                    "id": uuid.uuid4().hex, # EVENT ID
                    "type": "trace-create",
                    "timestamp": datetime.datetime.now().isoformat() + "Z",
                    "body": {
                        "id": trace_id, # TRACE ID
                        "name": "low_level_test_root",
                        "sessionId": session_id,
                        "userId": "low-level-user",
                        "metadata": {"test": True},
                        "tags": ["test"]
                    }
                }
            ]
        )
        print("Response:", res)
        
        # Now start an observation linked to it
        with lf.start_as_current_observation(
            name="low_level_child",
            trace_context={"trace_id": trace_id}
        ) as child:
            child.update(output="linked to low-level trace")
            
        lf.flush()
        print("Done.")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_low_level_trace()
