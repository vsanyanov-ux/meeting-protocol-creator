import os
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
import urllib.parse
from dotenv import load_dotenv
import shutil
import uuid
import subprocess
import logging

# Import our custom modules
from yandex_client import YandexClient
from protocol_generator import generate_docx
from email_client import send_email
from langfuse_client import PipelineTrace, submit_score

load_dotenv()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

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

# Initialize Yandex Client
yandex_client = YandexClient(
    api_key=os.getenv("YANDEX_API_KEY"),
    folder_id=os.getenv("YANDEX_FOLDER_ID"),
    s3_access_key=os.getenv("YANDEX_ACCESS_KEY"),
    s3_secret_key=os.getenv("YANDEX_SECRET_KEY"),
    s3_bucket=os.getenv("YANDEX_S3_BUCKET"),
    gpt_model=os.getenv("YANDEX_GPT_MODEL", "yandexgpt/latest")
)

UPLOAD_DIR = "uploads"
PROTOCOLS_DIR = "temp_protocols"
for d in [UPLOAD_DIR, PROTOCOLS_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# Simple in-memory status tracking
processing_status = {}

# --- Security: Validate required env vars on startup ---
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

@app.post("/process-meeting")
async def process_meeting(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Main endpoint to upload audio and trigger the protocol creation flow."""
    # 1. Validation
    extension = file.filename.split('.')[-1].lower()
    if extension not in ["mp3", "aac", "m4a", "wav"]:
        raise HTTPException(status_code=400, detail="Only MP3, AAC/M4A, and WAV formats are supported.")
    
    # 2. Save file locally
    file_id = str(uuid.uuid4())
    local_path = os.path.join(UPLOAD_DIR, f"{file_id}.{extension}")
    with open(local_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Initialize status
    processing_status[file_id] = {"status": "starting", "message": "File uploaded successfully"}
    
    # 3. Trigger processing in background
    background_tasks.add_task(run_full_pipeline, local_path, file_id)
    
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

    try:
        # A. Upload to S3 & Transcribe
        transcription = None
        has_s3 = all([yandex_client.s3_access_key, yandex_client.s3_secret_key, yandex_client.s3_bucket])

        if has_s3:
            processing_status[file_id] = {"status": "uploading", "message": "Uploading to secure cloud storage..."}
            trace.start_span("s3_upload", {"bucket": yandex_client.s3_bucket})
            object_name = f"meetings/{file_id}_{os.path.basename(local_path)}"
            file_url = yandex_client.upload_to_s3(local_path, object_name)
            trace.end_span("s3_upload", {"url_generated": bool(file_url)})

            if file_url:
                processing_status[file_id] = {"status": "transcribing", "message": "Transcribing audio (long operation)..."}
                trace.start_span("transcription_long", {"method": "async_s3"})
                transcription = yandex_client.transcribe_long(file_url)
                trace.end_span("transcription_long", {"chars": len(transcription) if transcription else 0})

        # B. Fallback to chunked transcription if no S3
        if not transcription:
            processing_status[file_id] = {"status": "transcribing", "message": "Processing long audio via chunking (No S3)..."}
            
            # 1. Create a workspace for chunks
            chunk_prefix = os.path.join(UPLOAD_DIR, f"chunks_{file_id}")
            if not os.path.exists(chunk_prefix):
                os.makedirs(chunk_prefix)
            
            try:
                # 2. Split audio into 25-second chunks in OggOpus format
                # -f segment: use segmenter
                # -segment_time 25: 25 seconds chunks
                # -c:a libopus: encode to Opus (SpeechKit v1 requirement)
                subprocess.run([
                    "ffmpeg", "-y", "-i", local_path, 
                    "-f", "segment", "-segment_time", "25",
                    "-c:a", "libopus", "-b:a", "24k", 
                    os.path.join(chunk_prefix, "chunk_%03d.ogg")
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # 3. Transcribe each chunk
                chunk_files = sorted([f for f in os.listdir(chunk_prefix) if f.endswith(".ogg")])
                transcription_parts = []
                
                for i, chunk_file in enumerate(chunk_files):
                    processing_status[file_id] = {"status": "transcribing", "message": f"Transcribing segment {i+1} of {len(chunk_files)}..."}
                    chunk_path = os.path.join(chunk_prefix, chunk_file)
                    with open(chunk_path, "rb") as f:
                        chunk_bytes = f.read()
                    
                    part = yandex_client.transcribe_short(chunk_bytes)
                    if part:
                        transcription_parts.append(part)
                
                transcription = " ".join(transcription_parts)
                
            except Exception as e:
                logger.error(f"Chunking/Transcription error: {e}")
                trace.end_span("transcription_chunked", {"error": str(e)}, level="ERROR")
            finally:
                # Cleanup chunks
                if os.path.exists(chunk_prefix):
                    shutil.rmtree(chunk_prefix)

        if not transcription:
            processing_status[file_id] = {"status": "error", "message": "Transcription failed. Please check your audio file and API keys."}
            trace.finish("error", {"stage": "transcription", "reason": "empty_result"})
            return

        # C. Create Protocol via Yandex GPT
        processing_status[file_id] = {"status": "generating", "message": "Analyzing meeting content and generating protocol..."}
        gpt_result = yandex_client.create_protocol(transcription)
        protocol_text = gpt_result["text"]

        # --- Langfuse: логируем LLM-вызов как Generation ---
        trace.log_generation(
            input_messages=gpt_result["messages"],
            output_text=protocol_text or "",
            model=yandex_client.gpt_model,
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

    except Exception as e:
        logger.error(f"Pipeline error for {file_id}: {e}")
        processing_status[file_id] = {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
        trace.finish("error", {"exception": str(e)})
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
