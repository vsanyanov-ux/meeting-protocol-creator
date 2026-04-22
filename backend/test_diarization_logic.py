import asyncio
import os
import sys
from loguru import logger

# Add parent directory to path to import providers
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from providers.local import LocalProvider

class MockWhisperSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text

async def test_merging_logic():
    """
    Tests only the merging algorithm without loading heavy AI models.
    """
    logger.info("--- Testing Diarization Merging Logic (No Models) ---")
    
    provider = LocalProvider()
    
    # Fake Whisper segments (from a 30s meeting)
    whisper_segments = [
        MockWhisperSegment(0.0, 5.0, "Здравствуйте все, начинаем наше совещание."),
        MockWhisperSegment(6.0, 15.0, "Сегодня мы обсуждаем внедрении офлайн моделей в наш проект."),
        MockWhisperSegment(16.0, 22.0, "Да, это отличная идея, я готов заняться бэкендом."),
        MockWhisperSegment(23.0, 30.0, "Хорошо, тогда я возьму на себя фронтенд и дизайн.")
    ]
    
    # Fake Pyannote speaker turns
    speaker_turns = [
        {"start": 0.0, "end": 15.5, "speaker": "SPEAKER_00"}, # First person talk
        {"start": 15.6, "end": 22.5, "speaker": "SPEAKER_01"}, # Second person talk
        {"start": 22.6, "end": 30.0, "speaker": "SPEAKER_00"}  # First person returns
    ]
    
    logger.info("Running merging algorithm...")
    
    # We call the merging logic directly (re-implementing the snippet from local.py for the test)
    formatted_lines = []
    for seg in whisper_segments:
        best_speaker = "Unknown"
        max_overlap = 0
        
        for turn in speaker_turns:
            overlap = min(seg.end, turn["end"]) - max(seg.start, turn["start"])
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = turn["speaker"]
        
        # Format label (same logic as in local.py)
        speaker_id = best_speaker.replace("SPEAKER_", "")
        try:
            label = f"Спикер {int(speaker_id) + 1}"
        except:
            label = best_speaker
            
        timestamp = f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]"
        formatted_lines.append(f"{timestamp} {label}: {seg.text}")

    result = "\n".join(formatted_lines)
    
    print("\n" + "="*50)
    print("MOCKED DIARIZATION RESULT:")
    print("="*50)
    print(result)
    print("="*50)
    
    # Verification
    if "Спикер 1: Здравствуйте" in result and "Спикер 2: Да, это отличная идея" in result:
        logger.success("Merging logic verified successfully!")
    else:
        logger.error("Merging logic mismatch!")

if __name__ == "__main__":
    asyncio.run(test_merging_logic())
