import asyncio
import os
import sys
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path to import providers
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from providers.local import LocalProvider

async def test_protocol_quality():
    load_dotenv()
    
    provider = LocalProvider(
        whisper_model_size=os.getenv("WHISPER_MODEL", "medium"),
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
    )

    logger.info(f"Using model: {provider.ollama_model}")

    # Complex transcription with multiple tasks
    test_transcription = """
    Иван (директор): Всем привет. Начинаем совещание по проекту КВеН-359Б. 
    Мария (инженер): Здравствуйте. У нас задержка по поставке сплава 08Х18Н10Т. Поставщик обещает привезти только через две недели.
    Иван: Это плохо. Мария, подготовьте официальную претензию поставщику до конца этой недели.
    Алексей (логист): Я могу поискать альтернативных поставщиков. Мне нужно 2 дня на анализ рынка.
    Иван: Хорошо, Алексей, к среде жду от тебя список альтернатив с ценами.
    Мария: Также нужно согласовать изменения в чертежах Т-100-2024.
    Иван: Мария, отправьте чертежи на согласование главному технологу сегодня до 18:00.
    На этом всё.
    """
    
    logger.info("--- Testing Protocol Generation Quality ---")
    try:
        result = await provider.create_protocol(test_transcription)
        if result["text"]:
            logger.success("Ollama generated a protocol!")
            
            # Save to file to avoid console encoding issues
            output_file = os.path.join(os.path.dirname(__file__), "last_protocol.md")
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(result["text"])
            
            logger.info(f"Protocol saved to {output_file}")
            
            # Validation checks
            text = result["text"]
            has_table = "|" in text and "-|-" in text
            is_russian = any("а" <= c.lower() <= "я" for c in text)
            
            if has_table:
                logger.success("PASSED: Output contains a Markdown table.")
            else:
                logger.error("FAILED: Output DOES NOT contain a Markdown table.")
                
            if is_russian:
                logger.success("PASSED: Output contains Russian characters.")
            else:
                logger.error("FAILED: Output DOES NOT seem to be in Russian.")
                
        else:
            logger.error("Ollama returned empty response.")
    except Exception as e:
        logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_protocol_quality())
