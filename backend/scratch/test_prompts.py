import os
import json
import sys
from loguru import logger

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langfuse_client import get_prompt

def test_local_prompts():
    logger.info("Testing local prompt loading...")
    
    # 1. Test existing local prompt
    p = get_prompt("meeting_create_protocol")
    if p and "Ты — профессиональный специалист" in p:
        logger.success("Successfully loaded 'meeting_create_protocol' from local cache!")
    else:
        logger.error("Failed to load 'meeting_create_protocol' from local cache.")

    # 2. Test variable replacement
    p_user = get_prompt("meeting_create_protocol_user", text="TEST_CONTENT", source_type="AUDIO", action_type="GENERATE")
    if "TEST_CONTENT" in p_user and "AUDIO" in p_user:
        logger.success("Variable replacement works!")
    else:
        logger.error(f"Variable replacement failed: {p_user}")

    # 3. Test fallback (if file missing)
    p_missing = get_prompt("non_existent_prompt", fallback="EMERGENCY_FALLBACK")
    if p_missing == "EMERGENCY_FALLBACK":
        logger.success("Fallback mechanism works!")
    else:
        logger.error(f"Fallback mechanism failed: {p_missing}")

if __name__ == "__main__":
    test_local_prompts()
