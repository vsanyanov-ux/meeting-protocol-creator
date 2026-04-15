import asyncio
import os
import sys
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path to import providers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from providers.local import LocalProvider

async def main():
    load_dotenv()
    
    provider = LocalProvider(
        whisper_model_size=os.getenv("WHISPER_MODEL", "medium"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    )

    logger.info("--- Testing GPU Detection ---")
    has_gpu = await provider._has_gpu()
    if has_gpu:
        logger.success("GPU detected! Whisper will run on CUDA.")
    else:
        logger.warning("GPU not detected. Whisper will fallback to CPU.")

    logger.info("--- Testing Ollama (Qwen) ---")
    test_transcription = "Привет! Сегодня мы обсуждаем запуск локальных моделей на RTX 3060. План: обновить конфиги и запустить бэкенд."
    
    try:
        result = await provider.create_protocol(test_transcription)
        if result["text"]:
            logger.success("Ollama successfully generated a protocol!")
            logger.info(f"Response snippet: {result['text'][:200]}...")
            logger.info(f"Latency: {result['latency_ms']}ms")
        else:
            logger.error("Ollama returned empty response.")
    except Exception as e:
        logger.error(f"Ollama test failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
