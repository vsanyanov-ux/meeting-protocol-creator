import os
import subprocess
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def extract_text_from_pdf(filepath: str) -> str:
    import pdfplumber
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text

def extract_text_from_docx(filepath: str) -> str:
    import docx
    doc = docx.Document(filepath)
    return "\n".join([p.text for p in doc.paragraphs])

def normalize_file(filepath: str, file_id: str) -> Dict[str, Any]:
    """
    Takes an input file and normalizes it based on its extension.
    Returns dict:
       {
           "type": "audio" | "text" | "error",
           "path": str (if audio),
           "content": str (if text),
           "error": Optional[str]
       }
    """
    ext = filepath.split(".")[-1].lower()
    
    # 1. Text Documents
    if ext == "txt":
        with open(filepath, "r", encoding="utf-8") as f:
            return {"type": "text", "content": f.read()}
            
    elif ext == "pdf":
        try:
            return {"type": "text", "content": extract_text_from_pdf(filepath)}
        except Exception as e:
            return {"type": "error", "error": f"Failed to parse PDF: {str(e)}"}
            
    elif ext == "docx":
        try:
            return {"type": "text", "content": extract_text_from_docx(filepath)}
        except Exception as e:
            return {"type": "error", "error": f"Failed to parse DOCX: {str(e)}"}

    # 2. Audio/Video -> Normalize to Opus OGG
    audio_video_exts = ["mp3", "mp4", "m4a", "aac", "wav", "webm", "mov", "avi", "ogg", "flac"]
    if ext in audio_video_exts:
        try:
            out_path = os.path.join(os.path.dirname(filepath), f"normalized_{file_id}.ogg")
            # Convert any audio/video to OggOpus, single channel, 16kHz (optimal for SpeechKit)
            # Remove video stream if present
            subprocess.run([
                "ffmpeg", "-y", "-i", filepath,
                "-c:a", "libopus", "-b:a", "24k", "-ac", "1", "-ar", "16000",
                "-vn", 
                out_path
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"type": "audio", "path": out_path}
        except Exception as e:
            logger.error(f"FFmpeg normalization error: {e}")
            return {"type": "error", "error": "Media normalization failed. Invalid or unsupported media file."}

    # 3. Unknown
    return {"type": "error", "error": f"Unsupported file extension: {ext}"}
