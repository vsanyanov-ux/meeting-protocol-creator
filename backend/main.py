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
from datetime import datetime

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
logger.add(sys.stdout, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>", enqueue=False)
logger.add("logs/app.log", rotation="10 MB", retention="10 days", compression="zip", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}", level="INFO", encoding="utf-8", enqueue=False)

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
global_pipeline_lock = asyncio.Lock()  # Serializes the entire pipeline for maximum stability
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
    # Startup logic: Clean up stale GPU lock from previous crashes
    lock_path = os.path.join("storage", "gpu.lock")
    if os.path.exists(lock_path):
        try:
            os.remove(lock_path)
            logger.warning("--- STARTUP: Cleaned up stale GPU lock file from previous session ---")
        except Exception as e:
            logger.error(f"--- STARTUP: Failed to remove stale GPU lock: {e} ---")

    # Clean up zombie tasks in DB
    status_manager.cleanup_zombie_tasks()

    provider_type = os.getenv("AI_PROVIDER", "yandex").lower()
    logger.info(f"Startup OK. Default provider: {provider_type}.")
    yield
    logger.info("Shutting down Протоколист API")

app = FastAPI(
    title="Протоколист API",
    version="5.1.0",
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

# --- Security: CORS ---
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
            whisper_model_size=os.getenv("WHISPER_MODEL", "large-v3-turbo"),
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen3.5:9b"),
            device=device
        )
    else:
        raise ValueError(f"Unknown AI_PROVIDER: {provider_type}")

ai_provider = get_provider()

UPLOAD_DIR = "uploads"
PROTOCOLS_DIR = "temp_protocols"
STORAGE_DIR = "storage"
for d in [UPLOAD_DIR, PROTOCOLS_DIR, STORAGE_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- Persistent Status Management ---
import sqlite3

class StatusManager:
    def __init__(self):
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)
        self.db_path = os.path.join(STORAGE_DIR, "status.db")
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    file_id TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def get(self, file_id: str) -> Dict[str, Any]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT data FROM tasks WHERE file_id = ?", (file_id,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.error(f"DB Error reading status for {file_id}: {e}")
        return {}

    def set(self, file_id: str, status: Dict[str, Any]):
        try:
            status_json = json.dumps(status, ensure_ascii=False)
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO tasks (file_id, data, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_id) DO UPDATE SET 
                        data = excluded.data,
                        updated_at = CURRENT_TIMESTAMP
                """, (file_id, status_json))
        except Exception as e:
            logger.error(f"DB Error writing status for {file_id}: {e}")

    def update(self, file_id: str, data: Dict[str, Any]):
        status = self.get(file_id)
        if not status and data.get("status") != "starting":
            return
        status.update(data)
        self.set(file_id, status)

    def cleanup_zombie_tasks(self):
        """Marks all tasks that were in progress as 'error' after a server restart."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                active_statuses = "('starting', 'uploading', 'transcribing', 'generating', 'verifying', 'emailing')"
                cursor = conn.execute(f"SELECT file_id, data FROM tasks WHERE json_extract(data, '$.status') IN {active_statuses}")
                zombies = cursor.fetchall()
                for file_id, data_json in zombies:
                    status = json.loads(data_json)
                    status["status"] = "error"
                    status["message"] = "Работа сервера была прервана. Пожалуйста, попробуйте запустить обработку снова."
                    conn.execute("UPDATE tasks SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE file_id = ?", (json.dumps(status, ensure_ascii=False), file_id))
                if zombies:
                    logger.info(f"Cleaned up {len(zombies)} zombie tasks.")
        except Exception as e:
            logger.error(f"Failed to cleanup zombie tasks: {e}")

    def get_all_active_count(self) -> int:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE data LIKE '%\"status\": \"processing\"%' OR data LIKE '%\"status\": \"transcribing\"%'")
                return cursor.fetchone()[0]
        except:
            return 0

status_manager = StatusManager()

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "tasks_in_queue": status_manager.get_all_active_count()
    }

@app.get("/info")
async def get_info():
    location_raw = os.getenv("BACKEND_LOCATION", "local").lower()
    return {
        "location": "Локально" if location_raw == "local" else "Онлайн",
        "default_provider": ai_provider.name,
        "is_online": location_raw == "online"
    }

@app.get("/")
async def root():
    return {"message": "Протоколист API is running"}

@app.get("/status/{file_id}")
async def get_status(file_id: str):
    status = status_manager.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="Processing task not found")
    return status

@app.get("/download/{file_id}")
async def download_protocol(file_id: str):
    status = status_manager.get(file_id)
    if not status or "docx_path" not in status:
        raise HTTPException(status_code=404, detail="DOCX file not found")
    docx_path = status.get("docx_path")
    filename = os.path.basename(docx_path)
    encoded_filename = urllib.parse.quote(filename)
    return FileResponse(
        path=docx_path, 
        filename=filename, 
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
    )

@app.post("/feedback/{file_id}")
async def submit_feedback(file_id: str, score: float = Form(...), comment: str = Form("")):
    ok = submit_score(file_id=file_id, score_name="user_rating", value=score, comment=comment)
    return {"status": "ok" if ok else "skipped"}

def cleanup_old_files(max_age_seconds: int = 86400):
    now = time.time()
    for directory in [UPLOAD_DIR, PROTOCOLS_DIR]:
        if not os.path.exists(directory): continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - max_age_seconds:
                try: os.remove(filepath)
                except: pass

@app.post("/process-meeting")
async def process_meeting(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(None),
    email: str = Form(None),
    provider: str = Form(None),
    existing_file_id: str = Form(None),
    force_cpu: bool = Form(False),
    session_id: str = Form(None),
    send_email: bool = Form(True)
):
    file_id = existing_file_id or str(uuid.uuid4())
    local_path = None
    if file:
        extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ""
        local_path = os.path.join(UPLOAD_DIR, f"{file_id}.{extension}" if extension else file_id)
        with open(local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        mime_type = magic.from_file(local_path, mime=True)
    else:
        possible_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(file_id)]
        if not possible_files: raise HTTPException(status_code=404, detail="File not found")
        local_path = os.path.join(UPLOAD_DIR, possible_files[0])
        mime_type = "reused-file"

    status_manager.set(file_id, {
        "status": "starting", 
        "message": "File received",
        "filename": file.filename if file else f"Retried-{file_id}"
    })

    metadata = {"file_id": file_id, "original_filename": file.filename if file else file_id}
    background_tasks.add_task(run_full_pipeline, local_path, file_id, metadata, email, provider, force_cpu, session_id, send_email)
    return {"status": "processing", "file_id": file_id}

class DummyTrace:
    def __getattr__(self, name):
        def dummy(*args, **kwargs): return None
        return dummy
    def __enter__(self): return self
    def __exit__(self, *args): pass

async def run_full_pipeline(local_path: str, file_id: str, metadata: dict = None, recipient_email: str = None, provider_type: str = None, force_cpu: bool = False, session_id: str = None, should_send_email: bool = True):
    """Orchestrates the full pipeline with a global lock for stability."""
    def emergency_log(msg):
        try:
            with open("logs/pipeline_debug.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} | {file_id} | {msg}\n")
        except: pass

    async with global_pipeline_lock:
        emergency_log("PIPELINE START (LOCKED)")
        try:
            current_provider = get_provider(provider_type, device="cpu" if force_cpu else None)
            from langfuse_client import PipelineTrace
            trace = None
            try:
                trace = PipelineTrace(file_id=file_id, filename=os.path.basename(local_path), provider=current_provider.name, metadata=metadata, session_id=session_id)
                with trace:
                    # 1. Normalization (CPU)
                    emergency_log("NORMALIZATION START")
                    status_manager.update(file_id, {"status": "starting", "message": "Подготовка файла..."})
                    trace.start_span("normalization")
                    norm_res = await asyncio.to_thread(normalize_file, local_path, file_id)
                    if norm_res.get("type") == "error": raise Exception(norm_res.get("error"))
                    trace.end_span("normalization")

                    transcription = None
                    protocol_text = None
                    audit_res = {}

                    # 2. AI Steps (GPU intensive, strictly sequential)
                    status_manager.update(file_id, {"status": "starting", "message": "В очереди GPU..."})
                    async with gpu_lock:
                        emergency_log("ACQUIRED GPU LOCK")
                        async with processing_semaphore:
                            emergency_log("ACQUIRED SEMAPHORE")
                            # A. STT
                            if norm_res["type"] == "text":
                                transcription = norm_res["content"]
                            else:
                                status_manager.update(file_id, {"status": "transcribing", "message": "Распознавание речи..."})
                                trace.start_span("transcription", as_type="generation")
                                transcription = await current_provider.transcribe_audio(
                                    norm_res["path"], file_id, 
                                    lambda s, m: status_manager.update(file_id, {"status": s, "message": m}), 
                                    trace
                                )
                                trace.end_span("transcription")
                            
                            if not transcription: raise Exception("Transcription failed")

                            # B. Protocol Generation
                            emergency_log("GENERATION START")
                            status_manager.update(file_id, {"status": "generating", "message": "Создание протокола..."})
                            trace.start_span("protocol_generation", as_type="generation")
                            gen_result = await current_provider.create_protocol(
                                transcription, 
                                lambda s, m: status_manager.update(file_id, {"status": s, "message": m}), 
                                file_id
                            )
                            protocol_text = gen_result.get("text")
                            emergency_log("GENERATION COMPLETE")
                            trace.log_generation(gen_result.get("messages", []), protocol_text, current_provider.model_name, gen_result.get("latency_ms", 0), gen_result.get("input_tokens", 0), gen_result.get("output_tokens", 0), "Create Protocol")
                            trace.end_span("protocol_generation")

                            # C. Audit
                            emergency_log("AUDIT START")
                            status_manager.update(file_id, {"status": "verifying", "message": "Аудит протокола..."})
                            trace.start_span("verification", as_type="generation")
                            audit_res = await current_provider.verify_protocol(transcription, protocol_text)
                            emergency_log("AUDIT COMPLETE")

                    emergency_log("GPU LOCK RELEASED")
                    # --- GPU RELEASED ---
                    # 3. Post-AI (Parallel)
                    status_manager.update(file_id, {"status": "generating", "message": "Формирование DOCX..."})
                    trace.start_span("docx_generation")
                    docx_path = await asyncio.to_thread(generate_docx, protocol_text)
                    trace.end_span("docx_generation", {"path": docx_path})

                    status_manager.update(file_id, {
                        "transcription": transcription, "protocol": protocol_text,
                        "verification_report": audit_res.get("verification_report", ""),
                        "scores": audit_res.get("scores", {}), "docx_path": docx_path
                    })

                    # Emailing
                    smtp_user = os.getenv("SMTP_USER")
                    if smtp_user and should_send_email:
                        status_manager.update(file_id, {"status": "emailing", "message": "Отправка на почту..."})
                        trace.start_span("email_send")
                        recipient = recipient_email or os.getenv("RECIPIENT_EMAIL", "vanyanov@yandex.ru")
                        success = await asyncio.to_thread(send_email, recipient, f"Протокол: {metadata.get('original_filename', 'Meeting')}", "Ваш протокол готов.", docx_path)
                        trace.end_span("email_send", {"success": success})
                        status_manager.update(file_id, {"status": "completed", "message": "Успех! Отправлено на почту." if success else "Протокол готов, почта не ушла."})
                        trace.finish("completed" if success else "email_error")
                    else:
                        status_manager.update(file_id, {"status": "completed", "message": "Успех!"})
                        trace.finish("completed")

                    # Cleanup
                    emergency_log("CLEANUP START")
                    for p in [local_path, norm_res.get("path")]:
                        try:
                            if p and os.path.exists(p): os.remove(p)
                        except Exception as ce:
                            emergency_log(f"CLEANUP ERROR for {p}: {ce}")
                    emergency_log("PIPELINE SUCCESS")
            except Exception as te:
                emergency_log(f"TRACE BLOCK ERROR: {te}")
                if trace: trace.finish(status="error")
                raise # Re-raise to be caught by outer try

        except Exception as e:
            emergency_log(f"PIPELINE CRITICAL ERROR: {str(e)}")
            logger.exception(f"Pipeline error for {file_id}: {e}")
            status_manager.update(file_id, {"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)
