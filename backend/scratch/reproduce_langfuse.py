import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
from langfuse_client import PipelineTrace
from loguru import logger
import time

load_dotenv()

def reproduce():
    logger.info("Starting reproduction trace...")
    
    with PipelineTrace(file_id="reproduce_issue_1") as trace:
        # 1. Normalization (Span)
        trace.start_span("normalization")
        time.sleep(0.1)
        trace.end_span("normalization", {"status": "success", "type": "audio"})
        
        # 2. Transcription (STT Generation)
        trace.log_stt(60.0) # logs as 'transcription' Generation
        
        # 3. Create Protocol (GPT Generation)
        logger.info("Logging create_protocol...")
        trace.log_generation(
            input_messages=[{"role": "user", "content": "Transcript text"}],
            output_text="Protocol text",
            model="yandexgpt/latest",
            latency_ms=2000,
            input_tokens=100,
            output_tokens=200
        )
        
        # 4. Email (Span)
        trace.start_span("email_send")
        time.sleep(0.1)
        trace.end_span("email_send", {"sent_to": "test@example.com"})
        
    logger.info("Done. Check Langfuse for 'normalization' and 'create_protocol'.")

if __name__ == "__main__":
    reproduce()
