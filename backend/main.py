import os
import sys
import io

# Force UTF-8 for Windows console (prevents UnicodeEncodeError with emojis/non-ascii)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Query, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
import urllib.parse
from dotenv import load_dotenv
import shutil
import uuid
import subprocess
import time
import asyncio
import json
import magic
from contextlib import asynccontextmanager
from loguru import logger
from typing import Optional, List, Dict, Any, Callable, Union
import traceback

# Import our custom modules
from providers.base import BaseAIProvider
from protocol_generator import generate_docx
from email_client import send_email
from langfuse_client import PipelineTrace, submit_score
from normalizer import normalize_file
from exceptions import HardwareError, ProviderQuotaError, ProviderNetworkError

load_dotenv()

# Logging setup
logger.remove()
# Use sink=sys.stdout to ensure it uses our UTF-8 wrapper
logger.add(sys.stdout, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", enqueue=True)
logger.add("logs/app.log", rotation="10 MB", retention="10 days", compression="zip", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}", level="INFO", encoding="utf-8")

# --- Cross-process Resource Locking ---
class GPULock:
    """Simple file-based spin-lock to coordinate GPU usage across multiple workers."""
    def __init__(self, lock_file: str = "storage/gpu.lock"):
        self.lock_file = lock_file

    async def __aenter__(self):
        while True:
            try:
                # Atomic file creation
                fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(time.time()).encode())
                os.close(fd)
                logger.info("GPU lock acquired by worker")
                return self
            except FileExistsError:
                # Check for stale lock (older than 1 hour)
                try:
                    if time.time() - os.path.getmtime(self.lock_file) > 3600:
                        os.remove(self.lock_file)
                        logger.warning("Released stale GPU lock")
                        continue
                except: pass
                await asyncio.sleep(2)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
                logger.info("GPU lock released by worker")
        except: pass

# --- Resource Limits ---
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", 1))
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
gpu_lock = GPULock()
logger.info(f"Initialized with MAX_CONCURRENT_TASKS = {MAX_CONCURRENT_TASKS} (per worker)")


# --- CUDA DLL Setup for Windows ---
def setup_cuda_dlls():
    if sys.platform == 'win32':
        import site
        # Add nvidia DLLs to path for faster-whisper/ctranslate2
        # On Windows, PIP installs DLLs into site-packages/nvidia/xxx/bin
        possible_sites = []
        try:
            possible_sites.extend(site.getsitepackages())
        except: pass
        
        try:
            user_site = site.getusersitepackages()
            if user_site:
                possible_sites.append(user_site)
        except: pass
            
        found_any = False
        for s in possible_sites:
            nvidia_bins = [
                os.path.join(s, "nvidia", "cublas", "bin"),
                os.path.join(s, "nvidia", "cudnn", "bin"),
                os.path.join(s, "nvidia", "cuda_nvrtc", "bin"),
                os.path.join(s, "nvidia", "cuda_runtime", "bin"),
            ]
            for p in nvidia_bins:
                if os.path.exists(p) and os.path.isdir(p):
                    try:
                        os.add_dll_directory(p)
                        logger.info(f"Added CUDA DLL directory: {p}")
                        found_any = True
                    except Exception as e:
                        logger.warning(f"Failed to add DLL directory {p}: {e}")
        
        if not found_any:
            logger.warning("No NVIDIA CUDA DLL directories found in site-packages. GPU transcription might fail if cuBLAS/cuDNN is not in system PATH.")

setup_cuda_dlls()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    provider_type = os.getenv("AI_PROVIDER", "yandex").lower()
    logger.info(f"Startup OK. Default provider: {provider_type}. CORS allowed origins: {ALLOWED_ORIGINS}")
    yield
    logger.info("Shutting down Протоколист API")

app = FastAPI(
    title="Протоколист API",
    version="4.2.0",
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
ALLOWED_ORIGINS = [
    "http://localhost:90",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:5177",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:90"
] + [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

def get_provider(provider_type: Optional[str] = None, device: Optional[str] = None) -> BaseAIProvider:
    if not provider_type:
        provider_type = os.getenv("AI_PROVIDER", "yandex").lower()
    else:
        provider_type = provider_type.lower()
    
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
    elif provider_type in ["local", "ollama"]:
        from providers.local import LocalProvider
        return LocalProvider(
            whisper_model_size=os.getenv("WHISPER_MODEL", "medium"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:4b"),
            device=device
        )

    else:
        raise ValueError(f"Unknown AI_PROVIDER: {provider_type}")

# Default provider for global info (backward compatibility)
ai_provider = get_provider()

UPLOAD_DIR = "uploads"
PROTOCOLS_DIR = "temp_protocols"
for d in [UPLOAD_DIR, PROTOCOLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- Persistent Status Management ---
class StatusManager:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = storage_dir
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir)

    def _get_path(self, file_id: str):
        return os.path.join(self.storage_dir, f"status_{file_id}.json")

    def get(self, file_id: str) -> Dict[str, Any]:
        path = self._get_path(file_id)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading status for {file_id}: {e}")
            return {}

    def set(self, file_id: str, status: Dict[str, Any]):
        path = self._get_path(file_id)
        temp_path = path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
            # Atomic replacement: prevents reading partial or locked files
            os.replace(temp_path, path)
        except Exception as e:
            logger.error(f"Error writing status for {file_id}: {e}")
            if os.path.exists(temp_path):
                try: os.remove(temp_path)
                except: pass

    def update(self, file_id: str, data: Dict[str, Any]):
        status = self.get(file_id)
        status.update(data)
        self.set(file_id, status)

    def get_all_active_count(self) -> int:
        count = 0
        try:
            for filename in os.listdir(self.storage_dir):
                if filename.startswith("status_"):
                    status = self.get(filename.replace("status_", "").replace(".json", ""))
                    if status.get("status") not in ["completed", "failed", "error"]:
                        count += 1
        except Exception:
            pass
        return count

status_manager = StatusManager()

# --- Security: Validate required env vars on startup ---
@app.get("/health")
async def health_check():
    """Standard health check endpoint for monitoring."""
    # We could add more checks here (e.g. Disk space, Yandex Cloud connectivity)
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "tasks_in_queue": status_manager.get_all_active_count()
    }

@app.get("/info")
async def get_info():
    """Returns information about the system configuration for the frontend."""
    location_raw = os.getenv("BACKEND_LOCATION", "local").lower()
    location_names = {
        "local": "Локально",
        "online": "Онлайн"
    }
    
    provider_mapping = {
        "yandex": "Яндекс Cloud",
        "local": "Локальный ИИ (GPU)"
    }
    
    return {
        "location": location_names.get(location_raw, "Неизвестно"),
        "default_provider": ai_provider.name,
        "provider_name": provider_mapping.get(ai_provider.name, ai_provider.name),
        "is_online": location_raw == "online"
    }



@app.get("/")
async def root():
    return {"message": "Протоколист API is running"}

@app.get("/status/{file_id}")
async def get_status(file_id: str):
    """Check the status of a specific processing task."""
    status = status_manager.get(file_id)
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
    status = status_manager.get(file_id)
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
    status = status_manager.get(file_id)
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
    request: Request,
    file: UploadFile = File(None), # Optional for retries
    email: str = Form(None),
    provider: str = Form(None),
    existing_file_id: str = Form(None),
    force_cpu: bool = Form(False)
):
    """Main endpoint to upload audio and trigger the protocol creation flow."""
    file_id = existing_file_id or str(uuid.uuid4())
    logger.info(f"Processing request: file_id={file_id}, email={email}, provider={provider}, has_file={file is not None}")
    local_path = None
    extension = None
    
    if file:
        parts = file.filename.split('.')
        extension = parts[-1].lower() if len(parts) > 1 else ""
        safe_ext = f".{extension}" if extension else ""
        local_path = os.path.join(UPLOAD_DIR, f"{file_id}{safe_ext}")
        
        # 2. Save file locally (Sync file writing is blocking, offload it)
        def save_file():
            with open(local_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        
        await asyncio.to_thread(save_file)
    else:
        # Check if file exists in UPLOAD_DIR
        possible_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(file_id)]
        if not possible_files:
            logger.warning(f"File not found for file_id: {file_id}. Request failed.")
            raise HTTPException(
                status_code=404, 
                detail=f"Existing file not found for ID {file_id}. If this was a new upload, the file was not received by the server. Please re-upload."
            )
        local_path = os.path.join(UPLOAD_DIR, possible_files[0])
        extension = local_path.split(".")[-1].lower() if "." in local_path else ""
    
    # 2.1 Deep Validation (MIME check) - This is the source of truth
    # magic.from_file is sync/blocking, offload it
    mime_type = "unknown"
    if file:
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
    else:
        mime_type = "reused-file"
    
    # 2.2 Initialize status ONLY if it's a new task or previously failed
    existing_status = status_manager.get(file_id)
    if not existing_status or existing_status.get("status") in ["error", "failed"]:
        logger.info(f"Initializing new status for file_id: {file_id}")
        status_manager.set(file_id, {
            "status": "starting", 
            "message": "File uploaded successfully",
            "filename": file.filename if file else f"Retried-{file_id}",
            "transcription": None,
            "verification_report": None,
            "docx_path": None
        })
    else:
        logger.info(f"Re-using existing status for file_id: {file_id} (current status: {existing_status.get('status')})")
    
    # 3. Collect metadata for Langfuse
    file_size = os.path.getsize(local_path)
    metadata = {
        "file_size": file_size,
        "mime_type": mime_type,
        "extension": extension or "unknown",
        "original_filename": file.filename if file else f"Retried-{file_id}",
        "force_cpu": force_cpu
    }

    # 4. Trigger processing in background ONLY IF NOT ALREADY PROCESSING
    if not existing_status or existing_status.get("status") in ["error", "failed", "completed"]:
        background_tasks.add_task(run_full_pipeline, local_path, file_id, metadata, email, provider, force_cpu)
        background_tasks.add_task(cleanup_old_files)
    else:
        logger.info(f"Pipeline for {file_id} is already running. Skipping redundant task trigger.")
    
    return {
        "status": "processing",
        "file_id": file_id,
        "message": "Audio is being transcribed and processed."
    }

async def run_full_pipeline(local_path: str, file_id: str, metadata: dict = None, recipient_email: str = None, provider_type: str = None, force_cpu: bool = False):
    """Full pipeline: S3 Upload (optional) -> STT -> GPT -> DOCX -> Email (optional)."""
    import traceback
    
    logger.info(f"run_full_pipeline STARTED for file_id={file_id}, path={local_path}, force_cpu={force_cpu}, provider={provider_type}")
    
    try:
        device_override = "cpu" if force_cpu else None
        current_provider = get_provider(provider_type, device=device_override)
        # --- Langfuse v4: используем контекстный менеджер для автоматического завершения трейса ---
        with PipelineTrace(
            file_id=file_id,
            filename=os.path.basename(local_path),
            provider=current_provider.name,
            metadata=metadata
        ) as trace:

            status_manager.update(file_id, {"status": "starting", "message": "Queued. Waiting for an available processing slot..."})
            
            async with gpu_lock:
                async with processing_semaphore:
                    # 1. Normalization Step
                    status_manager.update(file_id, {"status": "starting", "message": "Normalizing uploaded file..."})
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
                    status_manager.update(file_id, {"status": "error", "message": norm_res["error"]})
                    trace.finish("error", {"stage": "normalization", "reason": norm_res["error"]})
                    return

                transcription = None

                if norm_res["type"] == "text":
                    status_manager.update(file_id, {"status": "transcribing", "message": "Text document detected. Bypassing audio transcription..."})
                    transcription = norm_res["content"]
                    
                elif norm_res["type"] == "audio":
                    def status_updater(status: str, msg: str):
                        status_manager.update(file_id, {"status": status, "message": msg})
                    
                    try:
                        transcription = await current_provider.transcribe_audio(
                            audio_path=norm_res["path"], 
                            file_id=file_id, 
                            status_updater=status_updater, 
                            trace=trace
                        )
                    except HardwareError as he:
                        logger.warning(f"GPU FAILURE: {he}. Attempting automatic fallback to CPU...")
                        status_updater("transcribing", "GPU (CUDA) is unavailable or crashed. Automatically falling back to CPU mode...")
                        
                        # Re-initialize local provider forced to CPU
                        current_provider = get_provider("local", device="cpu")
                        
                        try:
                            transcription = await current_provider.transcribe_audio(
                                audio_path=norm_res["path"], 
                                file_id=file_id, 
                                status_updater=status_updater, 
                                trace=trace
                            )
                        except Exception as cpu_error:
                            logger.error(f"CPU Fallback also failed: {cpu_error}")
                            # Final fallback: Try Yandex Cloud if configured
                            if os.getenv("YANDEX_API_KEY"):
                                logger.info("Local CPU failed. Attempting final fallback: Cloud (Yandex)...")
                                status_updater("transcribing", "Local resources exhausted. Switching to Cloud processing...")
                                current_provider = get_provider("yandex")
                                transcription = await current_provider.transcribe_audio(
                                    audio_path=norm_res["path"], 
                                    file_id=file_id, 
                                    status_updater=status_updater, 
                                    trace=trace
                                )
                            else:
                                raise cpu_error

                    except Exception as e:
                        err_msg = f"Transcription crash: {str(e)}"
                        logger.error(err_msg)
                        trace.log_error("transcription", err_msg, traceback.format_exc())
                        raise e
                    
                if not transcription:
                    status_manager.update(file_id, {"status": "error", "message": "Transcription failed. Please check your audio file and API keys."})
                    trace.finish("error", {"stage": "transcription", "reason": "empty_result"})
                    return

                # Store transcription for manual review
                status_manager.update(file_id, {"transcription": transcription})

                # C. Create Protocol via Provider's GPT
                status_manager.update(file_id, {"status": "generating", "message": "Analyzing meeting content and generating protocol..."})
                
                try:
                    trace.start_span("Create Protocol")
                    gpt_result = await current_provider.create_protocol(transcription, status_updater=status_updater, file_id=file_id)
                    protocol_text = gpt_result["text"]

                    # --- Langfuse: логируем LLM-вызов как Generation ---
                    trace.log_generation(
                        input_messages=gpt_result["messages"],
                        output_text=protocol_text or "",
                        model=current_provider.model_name,
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
                    status_manager.set(file_id, {"status": "error", "message": "Protocol generation failed"})
                    trace.finish("error", {"stage": "gpt", "reason": "empty_result"})
                    return

                # C2. Automated Verification Step (Self-Critique)
                status_manager.update(file_id, {"status": "verifying", "message": "AI-Auditor is verifying protocol accuracy..."})
                
                try:
                    verify_res = await current_provider.verify_protocol(transcription, protocol_text)
                    status_manager.update(file_id, {"verification_report": verify_res["verification_report"]})
                    
                    # Log verification to Langfuse as a separate generation
                    trace.log_generation(
                        input_messages=[{"role": "user", "content": "Verify protocol"}],
                        output_text=verify_res["verification_report"],
                        model=f"{current_provider.model_name}_auditor",
                        latency_ms=verify_res.get("latency_ms", 0),
                        input_tokens=verify_res["input_tokens"],
                        output_tokens=verify_res["output_tokens"]
                    )
                    # Add Auditor's report to the protocol text so it appears in the DOCX
                    protocol_text += f"\n\n## ОТЧЕТ AI-АУДИТОРА\n{verify_res['verification_report']}"
                    
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
                    status_manager.update(file_id, {"status": "emailing", "message": "Sending protocol to your email..."})
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
                            body=f"Здравствуйте!\n\nПротокол совещания для файла '{orig_filename}' успешно сформирован и прикрепелен к этому письму.\n\nС уважением,\nПротоколист",
                            attachment_path=docx_path
                        )
                        trace.end_span("email_send", {"success": success, "recipient": recipient})
                    except Exception as e:
                        logger.error(f"Email login/send crash: {e}")
                        trace.log_error("email_send", str(e), traceback.format_exc())
                        success = False

                    if success:
                        status_manager.update(file_id, {
                            "status": "completed", 
                            "message": "Success! The protocol has been sent to your email.",
                            "docx_path": docx_path
                        })
                        trace.finish("completed", {"docx_path": docx_path, "email_sent": True})
                    else:
                        # IMPORTANT: Even if email fails, we mark as completed so user can download in UI
                        status_manager.update(file_id, {
                            "status": "completed", 
                            "message": "Protocol is ready! (Note: Email delivery failed, please download it here).",
                            "docx_path": docx_path
                        })
                        trace.finish("completed_with_email_error", {"docx_path": docx_path, "email_sent": False})
                else:
                    status_manager.update(file_id, {
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
        status_manager.update(file_id, {"status": "error", "message": f"An unexpected error occurred: {str(e)}"})
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    # Use 2 workers for better responsiveness (one for processing, one for heartbeats)
    # Note: On Windows, workers=N requires app to be passed as a string
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=2)
