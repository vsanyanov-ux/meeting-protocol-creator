import sys
import os
sys.path.append(os.getcwd())

from dotenv import load_dotenv
from langfuse_client import PipelineTrace
from loguru import logger
import time

# Загружаем окружение
load_dotenv()

def verify():
    logger.info("Starting manual verification trace for the user...")
    
    # Создаем трейс
    with PipelineTrace(file_id="verification_test_file") as trace:
        logger.info(f"Trace started: {trace.trace_id}")
        
        # 1. Проверяем обычный Span
        trace.start_span("check_step_1", {"action": "testing_spans"})
        time.sleep(0.5)
        trace.end_span("check_step_1", {"status": "ok"})
        
        # 2. Проверяем Генерацию (то, что не работало)
        logger.info("Logging dummy generation...")
        trace.log_generation(
            input_messages=[{"role": "user", "content": "How is the weather?"}],
            output_text="The weather is perfect for coding!",
            model="verification-model-v1",
            latency_ms=1200,
            input_tokens=10,
            output_tokens=20
        )
        
        # 3. Проверяем лог ошибки
        logger.info("Logging dummy error...")
        trace.log_error("verification_stage", "This is a test error to see if it links correctly")
        
    logger.info("Verification trace finished. Please check your Langfuse dashboard at https://us.cloud.langfuse.com/")

if __name__ == "__main__":
    verify()
