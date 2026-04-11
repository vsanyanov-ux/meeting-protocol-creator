import os
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Query, Form
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
import magic
from contextlib import asynccontextmanager
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

# Force UTF-8 for Windows console (prevents UnicodeEncodeError with emojis/non-ascii)
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    provider_type = os.getenv("AI_PROVIDER", "yandex").lower()
    if provider_type == "yandex":
        required_vars = ["YANDEX_API_KEY", "YANDEX_FOLDER_ID"]
        missing = [var for var in required_vars if not os.getenv(var)]
        if missing:
            raise RuntimeError(f"STARTUP ERROR: Missing required env vars for Yandex: {missing}")
    
    logger.info(f"Config OK. Provider: {provider_type}. CORS allowed origins: {ALLOWED_ORIGINS}")
    # MAX_UPLOAD_SIZE_BYTES is defined below, so we use a hardcoded or global check
    # But wait, ordering matters. Let's move MAX_UPLOAD_SIZE_BYTES up.
    
    yield
    logger.info("Shutting down PRO-Толк API")

app = FastAPI(
    title="PRO-Толк API",
    version="2.1.1",
    lifespan=lifespan
)

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
    elif provider_type == "local":
        from providers.local import LocalProvider
        return LocalProvider(
            whisper_model_size=os.getenv("WHISPER_MODEL", "medium"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3:7b")
        )
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

@app.get("/info")
async def get_info():
    """Returns information about the system configuration for the frontend."""
    location_raw = os.getenv("BACKEND_LOCATION", "local").lower()
    location_names = {
        "local": "Локально",
        "online": "Онлайн"
    }
    
    provider_names = {
        "yandex": "Яндекс GPT",
        "local": f"Local AI ({ai_provider.model_name})"
    }
    
    return {
        "location": location_names.get(location_raw, "Неизвестно"),
        "provider_name": provider_names.get(ai_provider.name, ai_provider.name),
        "is_online": location_raw == "online"
    }



@app.get("/")
async def root():
    return {"message": "PRO-Толк API is running"}

@app.get("/status/{file_id}")
async def get_status(file_id: str):
    """Check the status of a specific processing task."""
    status = processing_status.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="Processing task not found")
    
    # Return a safe copy of the status
    return {
        "status": status.get("status"),
        "message": status.get("message"),
        "docx_path": status.get("docx_path"),
        "transcription": status.get("transcription"),
        "verification_report": status.get("verification_report")
    }

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
async def process_meeting(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    email: str = Form(None)
):
    """Main endpoint to upload audio and trigger the protocol creation flow."""
    # 1. Basic Extension Check (Optional Hint)
    parts = file.filename.split('.')
    extension = parts[-1].lower() if len(parts) > 1 else ""
    file_id = str(uuid.uuid4())
    extension = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    safe_ext = f".{extension}" if extension else ""
    local_path = os.path.join(UPLOAD_DIR, f"{file_id}{safe_ext}")
    
    # 2. Save file locally (Sync file writing is blocking, offload it)
    def save_file():
        with open(local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    
    await asyncio.to_thread(save_file)
    
    # 2.1 Deep Validation (MIME check) - This is the source of truth
    # magic.from_file is sync/blocking, offload it
    try:
        mime_type = await asyncio.to_thread(magic.from_file, local_path, mime=True)
        logger.info(f"File uploaded: {file.filename}, detected MIME: {mime_type}")
        
        # Valid MIME types list (simplified)
        valid_mimes = [
            "audio/", "video/", "text/", 
            "application/pdf", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "application/vnd.ms-powerpoint",
            "application/octet-stream", # common fallback
            "application/x-zip-compressed", # occasionally for archives
            "inode/x-empty" # skip empty but don't crash
        ]
        
        # Check if MIME type is valid
        is_valid = any(mime_type.startswith(m) for m in valid_mimes)
        
        # Extension-based rejection (extra safety)
        forbidden_extensions = ["exe", "dll", "bin", "sh", "bat", "msi"]
        if extension in forbidden_extensions:
            if os.path.exists(local_path):
                os.remove(local_path)
            logger.warning(f"Rejected forbidden extension: {extension}")
            raise HTTPException(status_code=400, detail=f"Unsupported file extension: .{extension}")
        
        # Special case: some AAC/M4A files might be detected as audio/x-hx-aac-adts or similar
        if not is_valid and ("audio" in mime_type or "video" in mime_type or "mpeg" in mime_type):
            is_valid = True
            logger.info(f"Accepted {mime_type} as it contains 'audio/video/mpeg' keywords")

        if not is_valid:
            os.remove(local_path)
            logger.warning(f"Rejected file with invalid MIME type: {mime_type}")
            raise HTTPException(status_code=400, detail=f"Invalid file content. Detected: {mime_type}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"MIME validation error: {e}")
        # Continue if magic fails but log it
    
    # Initialize status with placeholders to avoid missing keys in frontend
    processing_status[file_id] = {
        "status": "starting", 
        "message": "File uploaded successfully",
        "transcription": None,
        "verification_report": None,
        "docx_path": None
    }
    
    # 3. Collect metadata for Langfuse
    file_size = os.path.getsize(local_path)
    metadata = {
        "file_size": file_size,
        "mime_type": mime_type,
        "extension": extension,
        "original_filename": file.filename
    }

    # 4. Trigger processing in background
    background_tasks.add_task(run_full_pipeline, local_path, file_id, metadata, email)
    background_tasks.add_task(cleanup_old_files)
    
    return {
        "status": "processing",
        "file_id": file_id,
        "message": "Audio is being transcribed and processed."
    }

async def run_full_pipeline(local_path: str, file_id: str, metadata: dict = None, recipient_email: str = None):
    """Full pipeline: S3 Upload (optional) -> STT -> GPT -> DOCX -> Email (optional)."""
    import traceback
    
    logger.info(f"run_full_pipeline STARTED for file_id={file_id}, path={local_path}")
    
    try:
        # --- Langfuse v4: используем контекстный менеджер для автоматического завершения трейса ---
        with PipelineTrace(
            file_id=file_id,
            filename=os.path.basename(local_path),
            provider=ai_provider.name,
            metadata=metadata
        ) as trace:

            processing_status[file_id].update({"status": "starting", "message": "Queued. Waiting for an available processing slot..."})
            
            async with processing_semaphore:
                # 1. Normalization Step
                processing_status[file_id].update({"status": "starting", "message": "Normalizing uploaded file..."})
                trace.start_span("normalization")
                
                try:
                    norm_res = await asyncio.to_thread(normalize_file, local_path, file_id)
                    trace.end_span("normalization", norm_res)
                except Exception as e:
                    err_msg = f"Normalization crash: {str(e)}"
                    logger.error(err_msg)
                    trace.log_error("normalization", err_msg, traceback.format_exc())
                    raise e

                if norm_res["type"] == "error":
                    processing_status[file_id].update({"status": "error", "message": norm_res["error"]})
                    trace.finish("error", {"stage": "normalization", "reason": norm_res["error"]})
                    return

                transcription = None

                if norm_res["type"] == "text":
                    processing_status[file_id].update({"status": "transcribing", "message": "Text document detected. Bypassing audio transcription..."})
                    transcription = norm_res["content"]
                    
                elif norm_res["type"] == "audio":
                    def status_updater(status: str, msg: str):
                        processing_status[file_id].update({"status": status, "message": msg})
                    
                    try:
                        transcription = await ai_provider.transcribe_audio(
                            audio_path=norm_res["path"], 
                            file_id=file_id, 
                            status_updater=status_updater, 
                            trace=trace
                        )
                    except Exception as e:
                        err_msg = f"Transcription crash: {str(e)}"
                        logger.error(err_msg)
                        trace.log_error("transcription", err_msg, traceback.format_exc())
                        raise e
                    
                if not transcription:
                    processing_status[file_id].update({"status": "error", "message": "Transcription failed. Please check your audio file and API keys."})
                    trace.finish("error", {"stage": "transcription", "reason": "empty_result"})
                    return

                # Store transcription for manual review
                processing_status[file_id]["transcription"] = transcription

                # C. Create Protocol via Provider's GPT
                processing_status[file_id].update({"status": "generating", "message": "Analyzing meeting content and generating protocol..."})
                
                try:
                    trace.start_span("Create Protocol")
                    gpt_result = await ai_provider.create_protocol(transcription)
                    protocol_text = gpt_result["text"]

                    # --- Langfuse: логируем LLM-вызов как Generation ---
                    trace.log_generation(
                        input_messages=gpt_result["messages"],
                        output_text=protocol_text or "",
                        model=ai_provider.model_name,
                        latency_ms=gpt_result["latency_ms"],
                        input_tokens=gpt_result["input_tokens"],
                        output_tokens=gpt_result["output_tokens"],
                        name="Create Protocol Generation"
                    )
                    trace.end_span("Create Protocol", {"success": bool(protocol_text)})
                except Exception as e:
                    err_msg = f"GPT Generation crash: {str(e)}"
                    logger.error(err_msg)
                    trace.log_error("gpt_generation", err_msg, traceback.format_exc())
                    raise e

                if not protocol_text:
                    processing_status[file_id] = {"status": "error", "message": "Protocol generation failed"}
                    trace.finish("error", {"stage": "gpt", "reason": "empty_result"})
                    return

                # C2. Automated Verification Step (Self-Critique)
                processing_status[file_id].update({"status": "verifying", "message": "AI-Auditor is verifying protocol accuracy..."})
                
                try:
                    verify_res = await ai_provider.verify_protocol(transcription, protocol_text)
                    processing_status[file_id]["verification_report"] = verify_res["verification_report"]
                    
                    # Log verification to Langfuse as a separate generation
                    trace.log_generation(
                        input_messages=[{"role": "user", "text": "Verify protocol"}],
                        output_text=verify_res["verification_report"],
                        model=f"{ai_provider.model_name}_auditor",
                        latency_ms=verify_res.get("latency_ms", 0),
                        input_tokens=verify_res["input_tokens"],
                        output_tokens=verify_res["output_tokens"]
                    )
                    
                    # --- Langfuse: отправляем автоматические оценки от Аудитора ---
                    if "scores" in verify_res and verify_res["scores"]:
                        for metric, value in verify_res["scores"].items():
                            trace.score(
                                name=f"ai_{metric}", 
                                value=float(value), 
                                comment="Автоматическая оценка AI-Аудитора"
                            )
                except Exception as e:
                    logger.warning(f"Self-verification failed: {e}")
                    trace.log_error("verification", str(e), traceback.format_exc())

                # D. Generate DOCX
                trace.start_span("docx_generation")
                try:
                    docx_path = await asyncio.to_thread(generate_docx, protocol_text)
                    trace.end_span("docx_generation", {"path": docx_path})
                except Exception as e:
                    err_msg = f"DOCX generation failed: {str(e)}"
                    logger.error(err_msg)
                    trace.log_error("docx_generation", err_msg, traceback.format_exc())
                    raise e

                # E. Send Email (Skip if no SMTP configured)
                smtp_user = os.getenv("SMTP_USER")
                if smtp_user:
                    processing_status[file_id].update({"status": "emailing", "message": "Sending protocol to your email..."})
                    trace.start_span("email_send")
                    # Recipient logic: 1. Passed manually, 2. Env var, 3. Default hardcoded
                    recipient = recipient_email or os.getenv("RECIPIENT_EMAIL", "vanyanov@yandex.ru")
                    try:
                        # Dynamic content to avoid spam filters
                        orig_filename = metadata.get("original_filename", "документа")
                        success = await asyncio.to_thread(
                            send_email,
                            recipient_email=recipient,
                            subject=f"Готов протокол совещания: {orig_filename}",
                            body=f"Здравствуйте!\n\nПротокол совещания для файла '{orig_filename}' успешно сформирован и прикрепелен к этому письму.\n\nС уважением,\nPRO-Толк",
                            attachment_path=docx_path
                        )
                        trace.end_span("email_send", {"success": success, "recipient": recipient})
                    except Exception as e:
                        logger.error(f"Email login/send crash: {e}")
                        trace.log_error("email_send", str(e), traceback.format_exc())
                        success = False

                    if success:
                        processing_status[file_id].update({
                            "status": "completed", 
                            "message": "Success! The protocol has been sent to your email.",
                            "docx_path": docx_path
                        })
                        trace.finish("completed", {"docx_path": docx_path, "email_sent": True})
                    else:
                        # IMPORTANT: Even if email fails, we mark as completed so user can download in UI
                        processing_status[file_id].update({
                            "status": "completed", 
                            "message": "Protocol is ready! (Note: Email delivery failed, please download it here).",
                            "docx_path": docx_path
                        })
                        trace.finish("completed_with_email_error", {"docx_path": docx_path, "email_sent": False})
                else:
                    processing_status[file_id].update({
                        "status": "completed", 
                        "message": f"Success! Protocol generated at {docx_path} (Email skipped, SMTP not configured).",
                        "docx_path": docx_path
                    })
                    trace.finish("completed", {"docx_path": docx_path, "email_sent": False})

                if os.path.exists(local_path):
                    await asyncio.to_thread(os.remove, local_path)
                if norm_res.get("path") and os.path.exists(norm_res["path"]):
                    await asyncio.to_thread(os.remove, norm_res["path"])

    except Exception as e:
        logger.error(f"Pipeline error for {file_id}: {e}")
        processing_status[file_id].update({"status": "error", "message": f"An unexpected error occurred: {str(e)}"})
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
