import asyncio
import os
import sys
from loguru import logger
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from providers.local import LocalProvider

async def main():
    load_dotenv()
    logger.info("Initializing LocalProvider to trigger Whisper download...")
    provider = LocalProvider(
        whisper_model_size=os.getenv("WHISPER_MODEL", "large-v3"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    )
    logger.info("Fetching Whisper model (this will start the download if not cached)...")
    await provider._get_whisper()
    logger.success("Whisper model is ready!")

if __name__ == "__main__":
    asyncio.run(main())
