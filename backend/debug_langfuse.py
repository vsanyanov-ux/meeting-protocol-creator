import os
import sys
import uuid
from loguru import logger

try:
    from langfuse import Langfuse
    print(f"IMPORT SUCCESS: {Langfuse}")
    
    # Имитируем загрузку из .env
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    if not pk or not sk:
        print("ERROR: Missing Langfuse keys in environment!")
        sys.exit(1)
        
    lf = Langfuse(public_key=pk, secret_key=sk, host=host)
    print(f"INSTANCE CREATED: {type(lf)}")
    
    trace_id = uuid.uuid4().hex
    print(f"TESTING START_OBSERVATION (trace_id: {trace_id})")
    
    # 1. Test trace creation
    obs = lf.start_observation(
        name="diagnostic_root",
        as_type="span",
        trace_context={"trace_id": trace_id}
    )
    print(f"ROOT OBSERVATION CREATED: {obs.id}")
    
    # 2. Test child nesting
    child = lf.start_observation(
        name="diagnostic_child",
        as_type="span",
        trace_context={
            "trace_id": trace_id,
            "parent_span_id": obs.id
        }
    )
    print(f"CHILD OBSERVATION CREATED: {child.id}")
    
    child.end()
    obs.end()
    
    # 3. Test scoring
    print("TESTING CREATE_SCORE")
    lf.create_score(trace_id=trace_id, name="diagnostic_check", value=1.0)
    print("SCORE CALL SUCCESS")

    lf.flush()
    print("DONE - Check your Langfuse dashboard for 'diagnostic_root'")
        
except Exception as e:
    print(f"DIAGNOSTIC FAILED: {e}")
    import traceback
    traceback.print_exc()
