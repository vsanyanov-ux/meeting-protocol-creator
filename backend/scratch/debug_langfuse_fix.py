import os
import time
import uuid
import datetime
from dotenv import load_dotenv
from loguru import logger
import sys

# Add current directory and backend directory to path
sys.path.append(os.getcwd())

from langfuse_client import PipelineTrace

def test_tracing():
    load_dotenv()
    
    # Check if keys are actually present
    pk = os.getenv("LANGFUSE_PUBLIC_KEY")
    sk = os.getenv("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        logger.error("LANGFUSE_PUBLIC_KEY or SECRET_KEY not found in .env")
        return

    logger.info("Starting tracing test...")
    
    file_id = str(uuid.uuid4())
    filename = "test_diag.mp3"
    
    with PipelineTrace(file_id=file_id, filename=filename, provider="test_diag") as trace:
        logger.info(f"Trace ID: {trace.trace_id}")
        
        # 1. Test Span
        logger.info("Testing Span: normalization")
        trace.start_span("normalization", {"mode": "high_quality"})
        time.sleep(0.5)
        trace.end_span("normalization", {"success": True})
        
        # 2. Test Generation (STT)
        logger.info("Testing Generation: transcription")
        trace.log_stt(duration_sec=30.0, model="whisper-v3")
        
        # 3. Test Generation (LLM)
        logger.info("Testing Generation: create_protocol")
        trace.log_generation(
            input_messages=[{"role": "user", "content": "summarize this"}],
            output_text="This is a summary. All good.",
            model="yandexgpt/test",
            latency_ms=1200,
            input_tokens=100,
            output_tokens=50
        )
        
        # 4. Test Error Log
        logger.info("Testing Error Log")
        trace.log_error("test_error", "Something went marginally wrong", "Wait, this is just a test.")
        
        # 5. Test Finish
        logger.info("Finishing Trace...")
        trace.finish("completed", {"overall": "success"})

    logger.info("Trace finished. Check Langfuse dashboard.")
    logger.info("Waiting 3 seconds for flush...")
    time.sleep(3)
    logger.info("Done.")

if __name__ == "__main__":
    test_tracing()
