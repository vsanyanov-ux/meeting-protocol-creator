import os
import json
import sys
from dotenv import load_dotenv
from loguru import logger

# Add parent directory to path to import langfuse_client
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langfuse_client import get_langfuse_client

load_dotenv()

PROMPTS_TO_UPLOAD = [
    "meeting_create_protocol",
    "meeting_create_protocol_user",
    "meeting_verify_protocol",
    "meeting_verify_protocol_user",
    "meeting_summarize_chunk",
    "meeting_summarize_chunk_user"
]

def upload_prompts():
    client = get_langfuse_client()
    if not client:
        logger.error("Langfuse client not initialized. Check your .env file.")
        return

    prompt_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")
    
    if not os.path.exists(prompt_dir):
        logger.error(f"Directory {prompt_dir} not found. Nothing to upload.")
        return

    success_count = 0
    for name in PROMPTS_TO_UPLOAD:
        local_path = os.path.join(prompt_dir, f"{name}.json")
        if not os.path.exists(local_path):
            logger.warning(f"File {local_path} not found, skipping...")
            continue

        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                prompt_text = data.get("prompt")
            
            if not prompt_text:
                logger.warning(f"No prompt text in {local_path}, skipping...")
                continue

            logger.info(f"Uploading new version for prompt: {name}...")
            
            # Use the Langfuse SDK to create a new version
            # Note: create_prompt will create a new version if the name already exists
            client.create_prompt(
                name=name,
                prompt=prompt_text
            )
            
            logger.success(f"Successfully uploaded {name} to Langfuse")
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to upload {name}: {e}")

    logger.info(f"Upload complete. {success_count}/{len(PROMPTS_TO_UPLOAD)} prompts updated in Langfuse.")

if __name__ == "__main__":
    upload_prompts()
