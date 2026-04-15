import os
import subprocess
import magic
from typing import Dict, Any
from loguru import logger

def extract_text_from_pdf(filepath: str) -> str:
    import pdfplumber
    text = ""
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        logger.error(f"pdfplumber error: {e}")
    return text

def extract_text_from_docx(filepath: str) -> str:
    import docx
    try:
        doc = docx.Document(filepath)
        return "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        logger.error(f"python-docx error: {e}")
        return ""

def normalize_file(filepath: str, file_id: str) -> Dict[str, Any]:
    """
    Takes an input file and normalizes it based on its MIME type.
    Returns dict:
       {
           "type": "audio" | "text" | "error",
           "path": str (if audio),
           "content": str (if text),
           "error": Optional[str]
       }
    """
    mime_type = magic.from_file(filepath, mime=True)
    logger.info(f"Normalizing file {file_id}. Detected MIME: {mime_type}")
    
    # 1. Text Documents (Direct content)
    ext = filepath.split(".")[-1].lower() if "." in filepath else ""
    is_media_ext = ext in ["mp3", "wav", "m4a", "ogg", "aac", "mp4", "m4v", "mov"]
    
    if mime_type == "text/plain" and not is_media_ext:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return {"type": "text", "content": f.read()}
        except UnicodeDecodeError:
            # Try some other common encodings for RU context
            try:
                with open(filepath, "r", encoding="cp1251") as f:
                    return {"type": "text", "content": f.read()}
            except:
                pass

    if mime_type == "application/pdf":
        return {"type": "text", "content": extract_text_from_pdf(filepath)}
            
    if "officedocument.wordprocessingml.document" in mime_type:
        return {"type": "text", "content": extract_text_from_docx(filepath)}

    # 2. Audio/Video -> Normalize to Opus OGG via FFmpeg
    # We accept almost any media type if FFmpeg can handle it
    is_media = any(m in mime_type for m in ["audio", "video", "mpeg", "octet-stream"])
    
    if is_media:
        try:
            out_path = os.path.join(os.path.dirname(filepath), f"normalized_{file_id}.ogg")
            result = subprocess.run([
                "ffmpeg", "-y", "-i", filepath,
                "-c:a", "libopus", "-b:a", "24k", "-ac", "1", "-ar", "16000",
                "-vn", 
                out_path
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return {"type": "audio", "path": out_path}
            else:
                logger.warning(f"FFmpeg failed to probe media, trying to read as text fallback: {result.stderr}")
        except Exception as e:
            logger.error(f"File normalization crash: {e}")

    # 3. Text fallback: Try reading as text if FFmpeg failed or MIME is generic
    try:
        # Check if it's small enough to be a text snippet or if we should try anyway
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            # If it's valid UTF-8 and not binary trash, we treat it as text
            if all(ord(c) < 65535 for c in content[:1000]):
                logger.info(f"Successfully recovered file {file_id} as text via fallback.")
                return {"type": "text", "content": content}
    except UnicodeDecodeError:
        pass
    except Exception as e:
        logger.debug(f"Text fallback failed: {e}")

    # 4. Last resort fallback for common extensions
    ext = filepath.split(".")[-1].lower() if "." in filepath else ""
    if ext in ["mp3", "wav", "m4a", "ogg", "aac", "mp4"]:
        try:
            out_path = os.path.join(os.path.dirname(filepath), f"normalized_{file_id}.ogg")
            subprocess.run(["ffmpeg", "-y", "-i", filepath, "-c:a", "libopus", "-vn", out_path], check=True)
            return {"type": "audio", "path": out_path}
        except:
            pass

    return {"type": "error", "error": f"Не удалось распознать содержимое файла ({mime_type})"}
