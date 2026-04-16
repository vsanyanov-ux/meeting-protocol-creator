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
    Takes an input file and normalizes it based on its MIME type and extension.
    Returns dict:
       {
           "type": "audio" | "text" | "error",
           "path": str (if audio),
           "content": str (if text),
           "error": Optional[str]
       }
    """
    mime_type = magic.from_file(filepath, mime=True)
    ext = filepath.split(".")[-1].lower() if "." in filepath else ""
    logger.info(f"Normalizing file {file_id}. MIME: {mime_type}, EXT: {ext}")
    
    # 1. Document Extraction by Extension (Priority for Windows/Generic MIME)
    if ext == "pdf":
        logger.info(f"Processing {file_id} as PDF via extension fallback")
        return {"type": "text", "content": extract_text_from_pdf(filepath)}
            
    if ext in ["docx", "doc"]:
        logger.info(f"Processing {file_id} as DOCX via extension fallback")
        return {"type": "text", "content": extract_text_from_docx(filepath)}
    
    if ext == "txt":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return {"type": "text", "content": f.read()}
        except:
            pass

    # 2. Document Extraction by MIME (Standard path)
    if mime_type == "application/pdf":
        return {"type": "text", "content": extract_text_from_pdf(filepath)}
            
    if "officedocument.wordprocessingml.document" in mime_type or mime_type == "application/msword":
        return {"type": "text", "content": extract_text_from_docx(filepath)}

    if mime_type == "text/plain":
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return {"type": "text", "content": f.read()}
        except UnicodeDecodeError:
            try:
                with open(filepath, "r", encoding="cp1251") as f:
                    return {"type": "text", "content": f.read()}
            except:
                pass

    # 3. Audio/Video -> Normalize to Opus OGG via FFmpeg
    # We accept media MIME types OR media extensions
    is_media_mime = any(m in mime_type for m in ["audio", "video", "mpeg"])
    is_media_ext = ext in ["mp3", "wav", "m4a", "ogg", "aac", "mp4", "m4v", "mov", "avi", "webm", "flac"]
    is_generic_binary = mime_type in ["application/octet-stream", "application/x-zip-compressed"]
    
    if is_media_mime or (is_generic_binary and is_media_ext):
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
                logger.warning(f"FFmpeg failed to process media {file_id}: {result.stderr}")
        except Exception as e:
            logger.error(f"File normalization crash: {e}")

    # 4. Text fallback: Try reading as text if FFmpeg failed or MIME is generic
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            # If it's valid UTF-8 and looks like text, we treat it as text
            if all(ord(c) < 65535 for c in content[:1000]):
                logger.info(f"Successfully recovered file {file_id} as text via fallback.")
                return {"type": "text", "content": content}
    except:
        pass

    return {"type": "error", "error": f"Не удалось распознать содержимое файла ({mime_type})"}
