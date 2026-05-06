import asyncio
import sys
import os

# Add parent dir to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from providers.local import LocalProvider
from providers.yandex import YandexProvider
from dotenv import load_dotenv

load_dotenv()

async def test_refinement():
    print("Testing Transcript Refinement...")
    
    # Mock transcript with common STT errors
    mock_transcript = "[00:12] Власть, привет. Как дела в цниитмаш?\n[00:15] Привет. Все хорошо, обсуждаем новые разработки."
    context = "Участники: Василий (Вася). Организация: ЦНИИТМАШ."
    
    provider_type = os.getenv("AI_PROVIDER", "local").lower()
    print(f"Using provider: {provider_type}")
    
    if provider_type == "local":
        provider = LocalProvider(
            whisper_model_size="tiny", # Tiny for fast check
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
        )
    else:
        provider = YandexProvider(
            api_key=os.getenv("YANDEX_API_KEY"),
            folder_id=os.getenv("YANDEX_FOLDER_ID")
        )
    
    print(f"Original: {mock_transcript}")
    print(f"Context: {context}")
    
    refined = await provider.refine_transcript(mock_transcript, context)
    
    print("\n" + "="*50)
    print("REFINED TRANSCRIPT:")
    print(refined)
    print("="*50)
    
    if "Василий" in refined or "Вася" in refined:
        print("\n✅ SUCCESS: 'власть' was likely fixed to 'Василий' or 'Вася'.")
    else:
        print("\n❌ FAILURE: Context terms not found in refined text.")

if __name__ == "__main__":
    asyncio.run(test_refinement())
