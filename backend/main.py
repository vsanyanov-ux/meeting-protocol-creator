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
import hashlib
import hashlib

# Import our custom modules
from providers.base import BaseAIProvider
from protocol_generator import generate_docx
from email_client import send_email
from langfuse_client import PipelineTrace, submit_score
from normalizer import normalize_file
from exceptions import HardwareError, ProviderQuotaError, ProviderNetworkError

# ADK Core Architecture Imports
from core.tools import get_agent_tool_declarations, TOOLS_REGISTRY
from core.adk_runtime import SessionContext, MeetingState, ADKAgentRunner

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
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", 50)) # Prevent queue flooding (Point 2)
processing_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
global_pipeline_lock = asyncio.Lock()  # Serializes the entire pipeline for maximum stability
gpu_lock = GPULock()
logger.info(f"Initialized with MAX_CONCURRENT_TASKS = {MAX_CONCURRENT_TASKS}, MAX_QUEUE_SIZE = {MAX_QUEUE_SIZE}")


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

def get_app_version():
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Пытаемся прочитать файл VERSION (для оффлайн продакшена)
        version_file = os.path.join(current_dir, "VERSION")
        if os.path.exists(version_file):
            with open(version_file, "r", encoding="utf-8") as f:
                ver = f.read().strip()
                if ver: return ver
                
        # Если файла нет, пытаемся достать версию через Git (для разработки)
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"], 
            cwd=os.path.dirname(current_dir),
            capture_output=True, text=True, check=True
        )
        ver = result.stdout.strip()
        if ver: return ver
    except Exception:
        pass
    # Фолбэк на случай ошибок
    return "5.7.1"

app_version = get_app_version()

app = FastAPI(
    title="Протоколист API",
    version=app_version,
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

# --- Security: Simple App Password (Point 1) ---
def verify_app_password(provided_password: str) -> bool:
    """Verifies provided password against SHA-256 hash or plain text in .env."""
    if not provided_password:
        return False
        
    stored_hash = os.getenv("APP_PASSWORD_HASH")
    if stored_hash:
        # Check against SHA-256 hash
        provided_hash = hashlib.sha256(provided_password.encode()).hexdigest()
        return provided_hash == stored_hash
    
    # Fallback to plain text APP_PASSWORD for legacy support
    app_pwd = os.getenv("APP_PASSWORD")
    if not app_pwd:
        return True # Access granted if no password configured
    return provided_password == app_pwd

@app.middleware("http")
async def check_app_password(request: Request, call_next):
    # Paths to exclude from password check
    public_paths = ["/", "/health", "/favicon.ico"]
    if request.url.path in public_paths:
        return await call_next(request)
    
    # Skip check if no password is configured at all
    if not os.getenv("APP_PASSWORD_HASH") and not os.getenv("APP_PASSWORD"):
        return await call_next(request)
    
    # Check for password in header or query param
    provided_pwd = request.headers.get("X-App-Password") or request.query_params.get("password")
    
    if not verify_app_password(provided_pwd):
        logger.warning(f"Unauthorized access attempt to {request.url.path} from {request.client.host}")
        return Response(
            content=json.dumps({"detail": "Несанкционированный доступ. Требуется правильный пароль."}, ensure_ascii=False),
            status_code=401,
            media_type="application/json"
        )
    
    return await call_next(request)

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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROTOCOLS_DIR = os.path.join(BASE_DIR, "temp_protocols")
STORAGE_DIR = os.path.join(BASE_DIR, "storage")
for d in [UPLOAD_DIR, PROTOCOLS_DIR, STORAGE_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

def is_safe_filename(filename: str) -> bool:
    """Checks if a filename is safe (no traversal, no suspicious chars)."""
    if not filename:
        return True
    # Only allow alphanumeric, underscore, hyphen and dot
    import re
    return bool(re.match(r'^[a-zA-Z0-9._-]+$', filename)) and ".." not in filename

def get_dir_size(path: str) -> int:
    """Returns total size of a directory in bytes."""
    total = 0
    with os.scandir(path) as it:
        for entry in it:
            if entry.is_file():
                total += entry.stat().st_size
    return total

MAX_TOTAL_UPLOADS_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB total limit

# --- Persistent Status Management ---
import sqlite3

class StatusManager:
    def __init__(self):
        if not os.path.exists(STORAGE_DIR):
            os.makedirs(STORAGE_DIR)
        # Use storage/ for SQLite to ensure persistence across container restarts
        self.db_path = os.path.join(STORAGE_DIR, 'status.db')
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL mode for concurrent read/write (Point 5)
            #conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout = 30000") # 30s timeout
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
        """Atomic update using transaction (Point 5)."""
        try:
            with sqlite3.connect(self.db_path, timeout=30) as conn:
                conn.execute("BEGIN IMMEDIATE") # Lock for writing
                cursor = conn.execute("SELECT data FROM tasks WHERE file_id = ?", (file_id,))
                row = cursor.fetchone()
                
                if not row and data.get("status") != "starting":
                    return
                
                status = json.loads(row[0]) if row else {}
                status.update(data)
                status_json = json.dumps(status, ensure_ascii=False)
                
                conn.execute("""
                    INSERT INTO tasks (file_id, data, updated_at) 
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_id) DO UPDATE SET 
                        data = excluded.data,
                        updated_at = CURRENT_TIMESTAMP
                """, (file_id, status_json))
        except Exception as e:
            logger.error(f"DB Error atomic updating status for {file_id}: {e}")

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
        """Returns the number of tasks currently being processed (any non-final state)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Count all tasks that are NOT in 'completed' or 'error' state
                cursor = conn.execute("SELECT COUNT(*) FROM tasks WHERE json_extract(data, '$.status') NOT IN ('completed', 'error')")
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            logger.error(f"Error counting active tasks: {e}")
            return 0

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns the list of successfully completed tasks."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT file_id, data, strftime('%Y-%m-%dT%H:%M:%SZ', updated_at) as updated_at 
                    FROM tasks 
                    WHERE json_extract(data, '$.status') = 'completed'
                    ORDER BY updated_at DESC 
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                history = []
                for row in rows:
                    file_id, data_json, updated_at = row
                    data = json.loads(data_json)
                    
                    # Check if file still exists on disk
                    docx_path = data.get("docx_path")
                    file_exists = os.path.exists(docx_path) if docx_path else False
                    
                    history.append({
                        "file_id": file_id,
                        "filename": data.get("filename", "Unknown"),
                        "status": data.get("status"),
                        "updated_at": updated_at,
                        "file_exists": file_exists,
                        "message": data.get("message")
                    })
                return history
        except Exception as e:
            logger.error(f"Error fetching history: {e}")
            return []

status_manager = StatusManager()

@app.get("/health")
async def health_check():
    # Get disk usage for the current directory
    usage = shutil.disk_usage(".")
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "tasks_in_queue": status_manager.get_all_active_count(),
        "disk_free_gb": round(usage.free / (1024**3), 2),
        "disk_total_gb": round(usage.total / (1024**3), 2),
        "disk_used_percent": round((usage.used / usage.total) * 100, 1)
    }

@app.get("/history")
async def get_history(limit: int = 50):
    """Returns the history of completed protocols."""
    return status_manager.get_history(limit=limit)

@app.get("/info")
async def get_info():
    location_raw = os.getenv("BACKEND_LOCATION", "local").lower()
    return {
        "location": "Локально" if location_raw == "local" else "Онлайн",
        "default_provider": ai_provider.name,
        "is_online": location_raw == "online",
        "version": app.version
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
async def submit_feedback(file_id: str, request: Request, score: Optional[float] = Form(None), comment: Optional[str] = Form("")):
    # Basic sanitization
    file_id = os.path.basename(file_id)
    if score is None:
        try:
            body = await request.json()
            score = float(body.get("score", 5.0))
            comment = body.get("comment", "")
        except Exception:
            score = 5.0
    ok = submit_score(file_id=file_id, score_name="user_rating", value=score, comment=comment or "")
    return {"status": "ok" if ok else "skipped"}

# ============================================================================
# ADK Standard Endpoints: Tool Declarations, State & Approval Gate
# ============================================================================

@app.get("/tools/declarations")
async def get_tool_declarations():
    """Возвращает Google ADK / Function Calling декларации всех инструментов."""
    return {
        "tools": get_agent_tool_declarations(),
        "total": len(TOOLS_REGISTRY)
    }

@app.get("/state/{file_id}")
async def get_meeting_state(file_id: str):
    """Возвращает структурированный ADK MeetingState задачи."""
    status = status_manager.get(file_id)
    if not status:
        raise HTTPException(status_code=404, detail="Meeting state not found")
    return status

@app.post("/approve/{file_id}")
async def approve_email_dispatch(file_id: str, background_tasks: BackgroundTasks):
    """
    ADK Approval Gate: оператор подтверждает отправку сформированного протокола на email.
    """
    raw_status = status_manager.get(file_id)
    if not raw_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if raw_status.get("status") != "waiting_for_approval":
        raise HTTPException(status_code=400, detail=f"Task is in status '{raw_status.get('status')}', not waiting for approval")
    
    session = SessionContext(session_id=str(uuid.uuid4()))
    state = MeetingState(
        file_id=file_id,
        filename=raw_status.get("filename", "Meeting"),
        status=raw_status.get("status"),
        docx_path=raw_status.get("docx_path"),
        recipient_email=raw_status.get("recipient_email"),
        should_send_email=True,
        email_approved=True
    )
    
    agent_runner = ADKAgentRunner(
        ai_provider=ai_provider,
        status_manager=status_manager,
        gpu_lock=gpu_lock,
        processing_semaphore=processing_semaphore,
        global_pipeline_lock=global_pipeline_lock
    )
    
    background_tasks.add_task(agent_runner.approve_and_dispatch_email, session, state)
    return {"status": "approved", "file_id": file_id, "message": "Отправка протокола подтверждена оператором."}

def cleanup_old_files(max_age_seconds: int = 86400):
    now = time.time()
    for directory in [UPLOAD_DIR, PROTOCOLS_DIR]:
        if not os.path.exists(directory): continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - max_age_seconds:
                try: os.remove(filepath)
                except: pass

ALLOWED_EXTENSIONS = {"mp3", "wav", "m4a", "aac", "ogg", "flac", "wma", "mp4", "mkv", "avi", "mov", "txt", "docx", "pdf", "doc"}

@app.post("/process-meeting")
async def process_meeting(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(None),
    email: str = Form(None),
    provider: str = Form(None),
    existing_file_id: str = Form(None),
    force_cpu: bool = Form(False),
    session_id: str = Form(None),
    should_send_email: bool = Form(True, alias="send_email"),
    context: str = Form(None)
):
    # 0. Check Queue Size (VRAM/Queue exhaustion protection)
    active_tasks = status_manager.get_all_active_count()
    if active_tasks >= MAX_QUEUE_SIZE:
        logger.warning(f"Rejecting request: queue full ({active_tasks}/{MAX_QUEUE_SIZE})")
        raise HTTPException(
            status_code=503, 
            detail="Сервер перегружен (слишком много задач в очереди). Пожалуйста, попробуйте через несколько минут."
        )

    # 1. Sanitize Inputs
    if existing_file_id:
        existing_file_id = os.path.basename(existing_file_id)
    
    file_id = existing_file_id or str(uuid.uuid4())
    
    # Proactive cleanup before each new task
    cleanup_old_files()

    local_path = None
    if file:
        raw_extension = file.filename.split('.')[-1].lower() if '.' in file.filename else ""
        import re
        extension = re.sub(r'[^a-z0-9]', '', raw_extension)
        if extension and extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file format. Неподдерживаемый формат файла.")
        
        current_usage = get_dir_size(UPLOAD_DIR)
        if current_usage > MAX_TOTAL_UPLOADS_SIZE_BYTES:
             raise HTTPException(status_code=507, detail="Превышена общая квота хранилища на сервере. Пожалуйста, попробуйте позже.")

        local_path = os.path.join(UPLOAD_DIR, f"{file_id}.{extension}" if extension else file_id)
        
        if not os.path.abspath(local_path).startswith(os.path.abspath(UPLOAD_DIR)):
            raise HTTPException(status_code=403, detail="Invalid file path")

        with open(local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        mime_type = magic.from_file(local_path, mime=True)
    else:
        possible_files = [f for f in os.listdir(UPLOAD_DIR) if f == file_id or f.startswith(f"{file_id}.")]
        if not possible_files: raise HTTPException(status_code=404, detail="File not found")
        local_path = os.path.join(UPLOAD_DIR, possible_files[0])
        mime_type = "reused-file"

    recipient = email or os.getenv("RECIPIENT_EMAIL", "vanyanov@yandex.ru")

    initial_meeting_state = MeetingState(
        file_id=file_id,
        filename=file.filename if file else f"Retried-{file_id}",
        local_path=local_path,
        media_type=mime_type,
        recipient_email=recipient,
        should_send_email=should_send_email
    )

    status_manager.set(file_id, initial_meeting_state.to_persistence_dict())

    metadata = {"file_id": file_id, "original_filename": file.filename if file else file_id}
    background_tasks.add_task(run_full_pipeline, local_path, file_id, metadata, recipient, provider, force_cpu, session_id, should_send_email, context)
    return {"status": "processing", "file_id": file_id}

async def run_full_pipeline(
    local_path: str, 
    file_id: str, 
    metadata: dict = None, 
    recipient_email: str = None, 
    provider_type: str = None, 
    force_cpu: bool = False, 
    session_id: str = None, 
    should_send_email: bool = True, 
    context: str = None
):
    """Оркестрирует выполнение агента через ADKAgentRunner."""
    current_provider = get_provider(provider_type, device="cpu" if force_cpu else None)
    
    session = SessionContext(
        session_id=session_id or str(uuid.uuid4()),
        metadata=metadata or {}
    )

    state = MeetingState(
        file_id=file_id,
        filename=metadata.get("original_filename", "Meeting") if metadata else "Meeting",
        local_path=local_path,
        recipient_email=recipient_email,
        should_send_email=should_send_email
    )

    runner = ADKAgentRunner(
        ai_provider=current_provider,
        status_manager=status_manager,
        gpu_lock=gpu_lock,
        processing_semaphore=processing_semaphore,
        global_pipeline_lock=global_pipeline_lock
    )

    trace = None
    try:
        from langfuse_client import PipelineTrace
        trace = PipelineTrace(
            file_id=file_id, 
            filename=os.path.basename(local_path), 
            provider=current_provider.name, 
            metadata=metadata, 
            session_id=session.session_id
        )
        with trace:
            await runner.run(session=session, state=state, context=context, trace=trace)
            
            # Smart VRAM Cleanup
            active_count = status_manager.get_all_active_count()
            if active_count <= 1:
                logger.info(f"--- SMART CLEANUP: Last task in queue ({file_id}). Clearing VRAM... ---")
                await current_provider.cleanup()
            
            trace.finish("completed")
    except Exception as e:
        logger.exception(f"ADK Pipeline critical error for {file_id}: {e}")
        if trace:
            trace.finish(status="error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, workers=1)
