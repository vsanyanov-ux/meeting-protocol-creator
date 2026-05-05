import os
import json
import sys
from dotenv import load_dotenv
from loguru import logger

# Add parent directory to path to import langfuse_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langfuse_client import get_langfuse_client

load_dotenv()

PROMPTS_TO_SYNC = [
    "meeting_create_protocol",
    "meeting_create_protocol_user",
    "meeting_verify_protocol",
    "meeting_verify_protocol_user",
    "meeting_summarize_chunk",
    "meeting_summarize_chunk_user",
    "meeting_humanize_speakers",
    "meeting_humanize_speakers_user"
]

def sync_prompts():
    client = get_langfuse_client()
    if not client:
        logger.error("Langfuse client not initialized. Check your .env file.")
        return

    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
    if not os.path.exists(prompt_dir):
        os.makedirs(prompt_dir)

    success_count = 0
    for name in PROMPTS_TO_SYNC:
        try:
            logger.info(f"Fetching prompt: {name}...")
            prompt = client.get_prompt(name)
            
            local_path = os.path.join(prompt_dir, f"{name}.json")
            data = {
                "name": name,
                "prompt": prompt.prompt,
                "version": getattr(prompt, "version", "latest"),
                "config": getattr(prompt, "config", {}),
                "synced_at": os.path.getmtime(__file__) if os.path.exists(__file__) else 0
            }
            
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.success(f"Successfully synced {name} to {local_path}")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to sync {name}: {e}")

    logger.info(f"Sync complete. {success_count}/{len(PROMPTS_TO_SYNC)} prompts updated.")

if __name__ == "__main__":
    sync_prompts()
