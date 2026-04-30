import os
from dotenv import load_dotenv
from langfuse import Langfuse, propagate_attributes
import uuid
import time

load_dotenv()

def test_clean_propagation():
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    lf = Langfuse(public_key=pk, secret_key=sk)
    
    trace_id = uuid.uuid4().hex
    session_id = f"clean-session-{uuid.uuid4().hex[:8]}"
    
    print(f"Testing CLEAN propagation with ID {trace_id} and session {session_id}")
    
    try:
        # Сначала стартуем корневое наблюдение
        with lf.start_as_current_observation(
            name="clean_root_trace",
            trace_context={"trace_id": trace_id}
        ) as root:
            
            # ВНУТРИ него устанавливаем атрибуты, гарантируя, что это СТРОКИ
            with propagate_attributes(
                session_id=str(session_id),
                user_id="clean-user@example.com",
                metadata={"env": "test", "version": "1.0"} # ТОЛЬКО СТРОКИ
            ):
                # Создаем дочерний спан
                with lf.start_as_current_observation(name="clean_child") as child:
                    child.update(output="This should have session_id inherited")
                    time.sleep(0.5)
        
        lf.flush()
        print("Done. Please check Sessions tab for:", session_id)
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_clean_propagation()
