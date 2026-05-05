import torch
import torchvision
import torch
import torchvision
import torch
import torchvision
import asyncio
import os
import sys
import time
from loguru import logger
from dotenv import load_dotenv

# Force UTF-8 output for Windows terminal
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path to import providers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from providers.local import LocalProvider

# Mock Trace object for testing
class MockTrace:
    def start_span(self, name): logger.info(f"SPAN START: {name}")
    def end_span(self, name, metadata=None): logger.info(f"SPAN END: {name} | Metadata: {metadata}")
    def log_error(self, name, error, tb=None): logger.error(f"ERROR in {name}: {error}")
    def log_stt(self, duration, model=None): logger.info(f"STT LOG: {duration}s | Model: {model}")
    def log_generation(self, messages, text, model, latency, input_tokens, output_tokens, name):
        logger.info(f"GENERATION LOG: {name} | Model: {model} | Tokens: {input_tokens}/{output_tokens}")
    def score(self, name, value): logger.info(f"SCORE: {name} = {value}")
    def finish(self, status, metadata=None): logger.info(f"TRACE FINISHED: {status}")

async def test_full_pipeline():
    load_dotenv()
    
    # Check for HF Token
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        logger.warning("HF_TOKEN missing in .env. Diarization will run in OFFLINE mode.")
    
    # Initialize Provider
    provider = LocalProvider(
        whisper_model_size=os.getenv("WHISPER_MODEL", "medium"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    )

    # 1. Get audio file from args or input
    print("\n" + "="*50)
    print("E2E DIARIZATION TEST")
    print("="*50)
    
    if len(sys.argv) > 1:
        audio_path = sys.argv[1]
    else:
        audio_path = input("Enter path to test audio file: ").strip()
        
    if not audio_path:
        audio_path = "test.wav"
        
    if not os.path.exists(audio_path):
        logger.error(f"File not found: {audio_path}")
        return

    # 2. Setup mock components
    def status_updater(status: str, msg: str):
        logger.info(f"STATUS [{status}]: {msg}")
    
    mock_trace = MockTrace()
    
    # 3. Start Transcription + Diarization
    logger.info(f"Starting E2E process for: {audio_path}")
    start_time = time.time()
    
    try:
        # This calls our new sequential pipeline: Ollama Unload -> Whisper -> Diarize -> Merging
        transcription = await provider.transcribe_audio(
            audio_path=audio_path,
            file_id="test_run",
            status_updater=status_updater,
            trace=mock_trace
        )
        
        if transcription:
            logger.success(f"Transcription complete! (Length: {len(transcription)} chars)")
            
            # Check if speakers were actually found (not just 'Unknown')
            if "Unknown" in transcription and "Спикер" not in transcription:
                logger.warning("Diarization ran but no speakers were identified (all marked as Unknown).")
            else:
                logger.success("Speakers identified successfully!")
            print("\n--- FINAL TRANSCRIPTION WITH SPEAKERS ---")
            print(transcription)
            print("-" * 40)
            
            # 4. Try Protocol Generation
            logger.info("Proceeding to Protocol Generation (Ollama)...")
            protocol_res = await provider.create_protocol(transcription)
            if protocol_res.get("text"):
                logger.success("Protocol generated successfully!")
                print("\n--- GENERATED PROTOCOL ---")
                print(protocol_res["text"])
                print("-" * 40)
                
                # 5. Try Protocol Verification (Nominal Auditor)
                logger.info("Proceeding to Protocol Verification (AI-Auditor)...")
                verify_res = await provider.verify_protocol(transcription, protocol_res["text"])
                
                if verify_res.get("verification_report"):
                    logger.success("Verification complete!")
                    print("\n--- AI-AUDITOR REPORT ---")
                    print(verify_res["verification_report"])
                    print("-" * 40)
                else:
                    logger.error("Verification failed.")
            else:
                logger.error("Protocol generation failed (empty response).")
        else:
            logger.error("Transcription/Diarization failed.")
            
    except Exception as e:
        logger.exception(f"FATAL ERROR DURING TEST: {e}")
    
    total_time = time.time() - start_time
    logger.info(f"Total processing time: {total_time:.1f}s")

if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
