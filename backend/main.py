import os
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import shutil
import uuid
import subprocess

# Import our custom modules
from yandex_client import YandexClient
from protocol_generator import generate_docx
from email_client import send_email

load_dotenv()

app = FastAPI(title="Meeting Protocol Creator API")

# CORS setup for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
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
    try:
        # A. Upload to S3 & Transcribe
        transcription = None
        has_s3 = all([yandex_client.s3_access_key, yandex_client.s3_secret_key, yandex_client.s3_bucket])
        
        if has_s3:
            processing_status[file_id] = {"status": "uploading", "message": "Uploading to secure cloud storage..."}
            object_name = f"meetings/{file_id}_{os.path.basename(local_path)}"
            file_url = yandex_client.upload_to_s3(local_path, object_name)
            
            if file_url:
                processing_status[file_id] = {"status": "transcribing", "message": "Transcribing audio (long operation)..."}
                transcription = yandex_client.transcribe_long(file_url)
        
        # B. Fallback to short transcription if no S3
        if not transcription:
            processing_status[file_id] = {"status": "transcribing", "message": "Transcribing audio (direct fallback without S3)..."}
            
            # Convert audio to OGG/Opus for Yandex API using FFmpeg (Yandex v1 expects OggOpus)
            ogg_path = local_path + ".ogg"
            try:
                subprocess.run(["ffmpeg", "-y", "-i", local_path, "-c:a", "libopus", "-b:a", "24k", ogg_path], 
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                with open(ogg_path, "rb") as audio:
                    audio_bytes = audio.read()
            except Exception as e:
                print("FFmpeg conversion failed:", e)
                with open(local_path, "rb") as audio:
                    audio_bytes = audio.read()
            
            transcription = yandex_client.transcribe_short(audio_bytes)
            
            if os.path.exists(ogg_path):
                os.remove(ogg_path)
        
        if not transcription:
            processing_status[file_id] = {"status": "error", "message": "Transcription failed. (Note: Without S3, max audio size is 1MB/30sec)"}
            return

        # C. Create Protocol via Yandex GPT
        processing_status[file_id] = {"status": "generating", "message": "Analyzing meeting content and generating protocol..."}
        protocol_text = yandex_client.create_protocol(transcription)
        if not protocol_text:
            processing_status[file_id] = {"status": "error", "message": "Protocol generation failed"}
            return

        # D. Generate DOCX
        docx_path = generate_docx(protocol_text)

        # E. Send Email (Skip if no SMTP configured)
        smtp_user = os.getenv("SMTP_USER")
        if smtp_user:
            processing_status[file_id] = {"status": "emailing", "message": "Sending protocol to your email..."}
            recipient = os.getenv("RECIPIENT_EMAIL", "v.s.anyanov@gmail.com")
            success = send_email(
                recipient_email=recipient,
                subject="Ваш протокол совещания готов",
                body="Здравствуйте!\n\nПротокол совещания сформирован и прикреплен к этому письму.\n\nС уважением,\nMeeting Protocol Creator",
                attachment_path=docx_path
            )
            
            if success:
                processing_status[file_id] = {"status": "completed", "message": "Success! The protocol has been sent to your email."}
            else:
                processing_status[file_id] = {"status": "error", "message": "Failed to send email. Process complete but delivery failed."}
        else:
            processing_status[file_id] = {"status": "completed", "message": f"Success! Protocol generated at {docx_path} (Email skipped, SMTP not configured)."}

        if os.path.exists(local_path): 
            os.remove(local_path)

    except Exception as e:
        print(f"Pipeline error for {file_id}: {e}")
        processing_status[file_id] = {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
    finally:
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
