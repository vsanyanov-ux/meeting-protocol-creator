import os
import sys
from loguru import logger
from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
import torch

def download_models():
    hf_token = os.getenv("HF_TOKEN")
    whisper_model_size = os.getenv("WHISPER_MODEL", "medium")
    
    # 1. Download Whisper
    logger.info(f"Downloading Whisper model: {whisper_model_size}...")
    try:
        # This will download the model to models_cache/whisper
        WhisperModel(
            whisper_model_size, 
            device="cpu", 
            compute_type="int8", 
            download_root="models_cache/whisper"
        )
        logger.info("Whisper model downloaded successfully.")
    except Exception as e:
        logger.error(f"Failed to download Whisper: {e}")
        # Don't exit yet, try pyannote

    # 2. Download Pyannote (if token present)
    if hf_token:
        logger.info("Downloading Pyannote diarization model...")
        try:
            # We use Pipeline.from_pretrained to cache the model
            # Note: By default it uses ~/.cache/huggingface or HF_HOME if set
            # The Dockerfile sets HF_HOME=/app/models_cache/huggingface
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=hf_token
            )
            logger.info("Pyannote model downloaded successfully.")
        except Exception as e:
            logger.error(f"Failed to download Pyannote: {e}")
            logger.warning("If you are building for offline use, diarization will not work without pre-downloaded weights.")
    else:
        logger.warning("HF_TOKEN missing. Skipping Pyannote pre-download.")

if __name__ == "__main__":
    download_models()
