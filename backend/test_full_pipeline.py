"""
Full pipeline test: Whisper Large-v3 → Qwen 3.5 9B
Run from the backend/ directory.
"""
import asyncio
import os
import sys
import time
from loguru import logger
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from providers.local import LocalProvider
from langfuse_client import PipelineTrace

AUDIO_PATH = os.path.join(os.path.dirname(__file__), "Test Audio", "test_audio.aac")

class DummyTrace:
    """Stub trace to avoid Langfuse dependency during testing."""
    def start_span(self, *a, **kw): pass
    def end_span(self, *a, **kw): pass
    def log_error(self, *a, **kw): pass

def status_updater(status: str, msg: str):
    logger.info(f"[{status.upper()}] {msg}")

async def main():
    load_dotenv()

    logger.info("=" * 60)
    logger.info("  FULL PIPELINE TEST: Whisper Large-v3 + Qwen 3.5 9B")
    logger.info("=" * 60)

    provider = LocalProvider(
        whisper_model_size=os.getenv("WHISPER_MODEL", "large-v3"),
        ollama_url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
    )

    if not os.path.exists(AUDIO_PATH):
        logger.error(f"Test audio not found: {AUDIO_PATH}")
        return

    logger.info(f"Audio file: {AUDIO_PATH} ({os.path.getsize(AUDIO_PATH) / 1024:.0f} KB)")

    # --- STEP 1: Transcription ---
    logger.info("\n--- STEP 1: TRANSCRIPTION (Whisper Large-v3) ---")
    t0 = time.time()
    try:
        transcription = await provider.transcribe_audio(
            audio_path=AUDIO_PATH,
            file_id="test_run",
            status_updater=status_updater,
            trace=DummyTrace()
        )
        t1 = time.time()
        logger.success(f"✅ Transcription complete in {t1 - t0:.1f}s")
        logger.info(f"Length: {len(transcription)} chars")
        logger.info(f"Preview: {transcription[:300]}...")
    except Exception as e:
        logger.error(f"❌ Transcription failed: {e}")
        return

    # --- STEP 2: Protocol Generation ---
    logger.info("\n--- STEP 2: PROTOCOL GENERATION (Qwen 3.5 9B) ---")
    t2 = time.time()
    try:
        result = await provider.create_protocol(
            transcription=transcription,
            status_updater=status_updater,
            file_id="test_run"
        )
        t3 = time.time()
        protocol = result.get("text", "")
        if protocol:
            logger.success(f"✅ Protocol generated in {t3 - t2:.1f}s")
            logger.info(f"Tokens: in={result.get('input_tokens',0)}, out={result.get('output_tokens',0)}")
            logger.info(f"\n{'='*60}\nPROTOCOL PREVIEW:\n{'='*60}\n{protocol[:800]}\n{'='*60}")
        else:
            logger.error("❌ Empty protocol returned.")
    except Exception as e:
        logger.error(f"❌ Protocol generation failed: {e}")
        return

    total = time.time() - t0
    logger.success(f"\n🏁 TOTAL PIPELINE TIME: {total:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
