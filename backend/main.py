import os
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
import urllib.parse
from dotenv import load_dotenv
import shutil
import uuid
import subprocess
import time
import sys
import asyncio
from loguru import logger

# Import our custom modules
from providers.base import BaseAIProvider
from protocol_generator import generate_docx
from email_client import send_email
from langfuse_client import PipelineTrace, submit_score
from normalizer import normalize_file

load_dotenv()

# Logging setup
logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
logger.add("logs/app.log", rotation="10 MB", retention="10 days", compression="zip", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}", level="INFO")

# --- Resource Limits ---
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", 2))
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
logger.info(f"Initialized with MAX_CONCURRENT_TASKS = {MAX_CONCURRENT_TASKS}")

app = FastAPI(title="Meeting Protocol Creator API")

# --- Security: File size limit middleware (500 MB) ---
MAX_UPLOAD_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_UPLOAD_SIZE_BYTES:
        return Response(
            content="Файл слишком большой. Максимальный размер: 500 МБ.",
            status_code=413
        )
    return await call_next(request)

# --- Security: CORS — только разрешённые origins ---
# Добавьте свой домен в ALLOWED_ORIGINS в .env
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def get_provider() -> BaseAIProvider:
    provider_type = os.getenv("AI_PROVIDER", "yandex").lower()
    
    if provider_type == "yandex":
        from providers.yandex import YandexProvider
        return YandexProvider(
            api_key=os.getenv("YANDEX_API_KEY"),
            folder_id=os.getenv("YANDEX_FOLDER_ID"),
            s3_access_key=os.getenv("YANDEX_ACCESS_KEY"),
            s3_secret_key=os.getenv("YANDEX_SECRET_KEY"),
            s3_bucket=os.getenv("YANDEX_S3_BUCKET"),
            gpt_model=os.getenv("YANDEX_GPT_MODEL", "yandexgpt/latest")
        )
    # elif provider_type == "local":
    #     from providers.local_whisper import LocalProvider
    #     return LocalProvider()
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {provider_type}")

ai_provider = get_provider()

UPLOAD_DIR = "uploads"
PROTOCOLS_DIR = "temp_protocols"
for d in [UPLOAD_DIR, PROTOCOLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# Simple in-memory status tracking
processing_status = {}

# --- Security: Validate required env vars on startup ---
@app.get("/health")
async def health_check():
    """Standard health check endpoint for monitoring."""
    # We could add more checks here (e.g. Disk space, Yandex Cloud connectivity)
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "tasks_in_queue": len(processing_status) - sum(1 for s in processing_status.values() if s.get("status") in ["completed", "failed"])
    }

@app.on_event("startup")
async def validate_config():
    required_vars = ["YANDEX_API_KEY", "YANDEX_FOLDER_ID"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise RuntimeError(
            f"ОШИБКА ЗАПУСКА: Отсутствуют обязательные переменные окружения: {missing}. "
            f"Проверьте файл .env"
        )
    logger.info(f"✅ Config OK. CORS allowed origins: {ALLOWED_ORIGINS}")
    logger.info(f"✅ Upload size limit: {MAX_UPLOAD_SIZE_BYTES // (1024*1024)} MB")


@app.get("/")
async def root():
    return {"message": "Meeting Protocol Creator API is running"}

@app.get("/status/{file_id}")
async def get_status(file_id: str):
    """Check the status of a specific processing task."""
    status = processing_status.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="Processing task not found")
    return status

@app.get("/download/{file_id}")
async def download_protocol(file_id: str):
    """Download the generated DOCX file."""
    status = processing_status.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="File ID not found")
    
    if status.get("status") != "completed" and "docx_path" not in status:
        raise HTTPException(status_code=400, detail="Protocol is not ready yet")
        
    docx_path = status.get("docx_path")
    if not docx_path or not os.path.exists(docx_path):
        raise HTTPException(status_code=404, detail="DOCX file not found on server")
        
    filename = os.path.basename(docx_path)
    # RFC 5987: properly encode non-ASCII characters in filename
    encoded_filename = urllib.parse.quote(filename)
    
    return FileResponse(
        path=docx_path, 
        filename=filename, 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )


from pydantic import BaseModel, Field

class FeedbackRequest(BaseModel):
    score: float = Field(..., ge=1.0, le=5.0, description="Оценка качества протокола (1-5)")
    comment: str = Field("", max_length=1000, description="Комментарий")
    score_name: str = Field("user_rating", description="Название метрики")

@app.post("/feedback/{file_id}")
async def submit_feedback(file_id: str, body: FeedbackRequest):
    """
    Отправить оценку качества протокола в Langfuse.
    score_name может быть: 'user_rating', 'protocol_completeness', 'formatting_quality'
    """
    status = processing_status.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    ok = submit_score(
        file_id=file_id,
        score_name=body.score_name,
        value=body.score,
        comment=body.comment
    )
    if ok:
        return {"status": "ok", "message": "Оценка отправлена в Langfuse"}
    else:
        # Langfuse не настроен — не ошибка, просто не записываем
        return {"status": "skipped", "message": "Langfuse не настроен, оценка не сохранена"}

def cleanup_old_files(max_age_seconds: int = 86400):
    """Deletes files in UPLOAD_DIR and PROTOCOLS_DIR older than max_age_seconds."""
    now = time.time()
    for directory in [UPLOAD_DIR, PROTOCOLS_DIR]:
        if not os.path.exists(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            # Skip directories like chunks_xxx unless they are also old, but let's just delete files for now.
            if os.path.isfile(filepath):
                try:
                    if os.stat(filepath).st_mtime < now - max_age_seconds:
                        os.remove(filepath)
                        logger.info(f"Cleaned up old file: {filepath}")
                except Exception as e:
                    logger.error(f"Failed to clean up file {filepath}: {e}")
            elif os.path.isdir(filepath) and filename.startswith("chunks_"):
                # Prune old chunk directories
                try:
                    if os.stat(filepath).st_mtime < now - max_age_seconds:
                        shutil.rmtree(filepath)
                        logger.info(f"Cleaned up old chunk dir: {filepath}")
                except Exception as e:
                    logger.error(f"Failed to clean up dir {filepath}: {e}")

@app.post("/process-meeting")
async def process_meeting(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Main endpoint to upload audio and trigger the protocol creation flow."""
    # 1. Validation
    extension = file.filename.split('.')[-1].lower()
    allowed_exts = ["mp3", "aac", "m4a", "wav", "mp4", "webm", "mov", "avi", "ogg", "flac", "txt", "pdf", "docx"]
    if extension not in allowed_exts:
        raise HTTPException(status_code=400, detail="Unsupported file format.")
    
    # 2. Save file locally
    file_id = str(uuid.uuid4())
    local_path = os.path.join(UPLOAD_DIR, f"{file_id}.{extension}")
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2.1 Deep Validation (MIME check)
    try:
        mime_type = magic.from_file(local_path, mime=True)
        logger.info(f"File uploaded: {file.filename}, detected MIME: {mime_type}")
        
        # Valid MIME types list (simplified)
        valid_mimes = [
            "audio/", "video/", "text/plain", 
            "application/pdf", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/octet-stream" # some browsers send this for specific audio
        ]
        
        if not any(mime_type.startswith(m) for m in valid_mimes):
            os.remove(local_path)
            logger.warning(f"Rejected file with invalid MIME type: {mime_type}")
            raise HTTPException(status_code=400, detail=f"Invalid file content. Detected: {mime_type}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MIME validation error: {e}")
        # Continue if magic fails but log it
    
    # Initialize status
    processing_status[file_id] = {"status": "starting", "message": "File uploaded successfully"}
    
    # 3. Trigger processing in background
    background_tasks.add_task(run_full_pipeline, local_path, file_id)
    background_tasks.add_task(cleanup_old_files)
    
    return {
        "status": "processing",
        "file_id": file_id,
        "message": "Audio is being transcribed and processed."
    }

async def run_full_pipeline(local_path: str, file_id: str):
    """Full pipeline: S3 Upload (optional) -> STT -> GPT -> DOCX -> Email (optional)."""

    # --- Langfuse: создаём trace на весь pipeline ---
    trace = PipelineTrace(
        file_id=file_id,
        filename=os.path.basename(local_path),
        provider="yandex"
    )

    processing_status[file_id] = {"status": "starting", "message": "Queued. Waiting for an available processing slot..."}
    
    try:
        async with processing_semaphore:
            # 1. Normalization Step
            processing_status[file_id] = {"status": "starting", "message": "Normalizing uploaded file..."}
            trace.start_span("normalization")
            
            # Since normalizer is synchronous, we run it in a threadpool to prevent event loop blocking
            # But for simplicity, we call it directly (assume fast execution or mostly subprocess)
            norm_res = normalize_file(local_path, file_id)
            trace.end_span("normalization", norm_res)

            if norm_res["type"] == "error":
                processing_status[file_id] = {"status": "error", "message": norm_res["error"]}
                trace.finish("error", {"stage": "normalization", "reason": norm_res["error"]})
                return

            transcription = None

            if norm_res["type"] == "text":
                processing_status[file_id] = {"status": "transcribing", "message": "Text document detected. Bypassing audio transcription..."}
                transcription = norm_res["content"]
                
            elif norm_res["type"] == "audio":
                def status_updater(status: str, msg: str):
                    processing_status[file_id] = {"status": status, "message": msg}
                    
                transcription = ai_provider.transcribe_audio(
                    audio_path=norm_res["path"], 
                    file_id=file_id, 
                    status_updater=status_updater, 
                    trace=trace
                )
                
            if not transcription:
                processing_status[file_id] = {"status": "error", "message": "Transcription failed. Please check your audio file and API keys."}
                trace.finish("error", {"stage": "transcription", "reason": "empty_result"})
                return

            # C. Create Protocol via Provider's GPT
            processing_status[file_id] = {"status": "generating", "message": "Analyzing meeting content and generating protocol..."}
            gpt_result = ai_provider.create_protocol(transcription)
            protocol_text = gpt_result["text"]

            # --- Langfuse: логируем LLM-вызов как Generation ---
            trace.log_generation(
                input_messages=gpt_result["messages"],
                output_text=protocol_text or "",
                model=ai_provider.name,
                latency_ms=gpt_result["latency_ms"],
                input_tokens=gpt_result["input_tokens"],
                output_tokens=gpt_result["output_tokens"],
            )

            if not protocol_text:
                processing_status[file_id] = {"status": "error", "message": "Protocol generation failed"}
                trace.finish("error", {"stage": "gpt", "reason": "empty_result"})
                return

            # D. Generate DOCX
            trace.start_span("docx_generation")
            docx_path = generate_docx(protocol_text)
            trace.end_span("docx_generation", {"path": docx_path})

            # E. Send Email (Skip if no SMTP configured)
            smtp_user = os.getenv("SMTP_USER")
            if smtp_user:
                processing_status[file_id] = {"status": "emailing", "message": "Sending protocol to your email..."}
                trace.start_span("email_send")
                recipient = os.getenv("RECIPIENT_EMAIL", "v.s.anyanov@gmail.com")
                success = send_email(
                    recipient_email=recipient,
                    subject="Ваш протокол совещания готов",
                    body="Здравствуйте!\n\nПротокол совещания сформирован и прикреплен к этому письму.\n\nС уважением,\nMeeting Protocol Creator",
                    attachment_path=docx_path
                )
                trace.end_span("email_send", {"success": success, "recipient": recipient})

                if success:
                    processing_status[file_id] = {
                        "status": "completed", 
                        "message": "Success! The protocol has been sent to your email.",
                        "docx_path": docx_path
                    }
                    trace.finish("completed", {"docx_path": docx_path, "email_sent": True})
                else:
                    processing_status[file_id] = {
                        "status": "error", 
                        "message": "Failed to send email. Process complete but delivery failed.",
                        "docx_path": docx_path # Добавляем путь даже если email не ушел, чтобы можно было скачать
                    }
                    trace.finish("email_error", {"docx_path": docx_path, "email_sent": False})
            else:
                processing_status[file_id] = {
                    "status": "completed", 
                    "message": f"Success! Protocol generated at {docx_path} (Email skipped, SMTP not configured).",
                    "docx_path": docx_path
                }
                trace.finish("completed", {"docx_path": docx_path, "email_sent": False})

            if os.path.exists(local_path):
                os.remove(local_path)
            if norm_res.get("path") and os.path.exists(norm_res["path"]):
                os.remove(norm_res["path"])

    except Exception as e:
        logger.error(f"Pipeline error for {file_id}: {e}")
        processing_status[file_id] = {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
        trace.finish("error", {"exception": str(e)})
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
