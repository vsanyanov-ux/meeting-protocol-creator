import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.getcwd())

from langfuse_client import PipelineTrace

def quick_verify():
    print("Starting Langfuse verification...")
    load_dotenv()
    
    # Create test trace
    with PipelineTrace(file_id="manual_test_check", filename="verify.mp3") as trace:
        if not trace.lf:
            print("ERROR: Langfuse not configured (check .env)")
            return

        print(f"Trace created: {trace.trace_id}")
        
        # 1. Log STT (120 seconds)
        print("Logging STT (120 sec)...")
        trace.log_stt(duration_sec=120.0)
        
        # 2. Log GPT (1500 tokens)
        print("Logging GPT (1500 tokens)...")
        trace.log_generation(
            input_messages=[{"role": "user", "content": "test"}],
            output_text="test response",
            input_tokens=500,
            output_tokens=1000
        )
        
        print(f"Total calculated cost: ${trace.total_cost:.6f}")
        trace.lf.flush()
        
    print("\nDONE! Please check Langfuse Traces UI.")

if __name__ == "__main__":
    quick_verify()
