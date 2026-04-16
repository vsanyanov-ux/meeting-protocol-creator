import pytest
import os
import time
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from main import app
from docx import Document

# Paths to test assets
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "test_assets")
AUDIO_PATH = os.path.join(ASSETS_DIR, "sample_audio.aac")
VIDEO_PATH = os.path.join(ASSETS_DIR, "sample_video.mp4")
TXT_PATH = os.path.join(ASSETS_DIR, "sample.txt")
DOCX_PATH = os.path.join(ASSETS_DIR, "sample_doc.docx")

@pytest.fixture
def client():
    return TestClient(app)

def poll_status(client, file_id):
    """Helper to poll status until terminal state."""
    for _ in range(20):
        resp = client.get(f"/status/{file_id}")
        data = resp.json()
        if data["status"] in ["completed", "error"]:
            return data
        time.sleep(0.5)
    return data

@pytest.mark.no_mock
@pytest.mark.parametrize("provider", ["local", "yandex"])
@pytest.mark.parametrize("format_info", [
    ("txt", TXT_PATH, "text/plain"),
    ("docx", DOCX_PATH, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("aac", AUDIO_PATH, "audio/aac"),
    ("mp4", VIDEO_PATH, "video/mp4"),
])
def test_e2e_formats_and_providers(client, provider, format_info):
    """Exhaustive test for representative formats across both providers."""
    ext, path, mime = format_info
    
    with patch("main.get_provider") as mock_get_provider, \
         patch("main.PipelineTrace") as mock_trace, \
         patch("main.send_email") as mock_email:
        
        mock_provider = MagicMock()
        mock_provider.name = f"mock-{provider}"
        mock_provider.transcribe_audio = AsyncMock(return_value={"text": f"Transcript for {ext}", "segments": []})
        mock_provider.create_protocol = AsyncMock(return_value={
            "text": f"## Protocol\nFormat: {ext}, Provider: {provider}",
            "latency_ms": 10,
            "input_tokens": 100,
            "output_tokens": 100,
            "messages": []
        })
        mock_provider.verify_protocol = AsyncMock(return_value={
            "verification_report": "OK",
            "input_tokens": 10,
            "output_tokens": 10,
            "scores": {"completeness": 5, "accuracy": 5, "hallucinations": 5}
        })
        mock_provider.format_transcript_with_ai = AsyncMock(return_value={"formatted_text": "fmt"})
        mock_get_provider.return_value = mock_provider
        
        # 1. Upload
        with open(path, "rb") as f:
            response = client.post("/process-meeting", 
                                   files={"file": (f"test.{ext}", f, mime)},
                                   data={"provider": provider, "email": "test@user.com"})
        
        assert response.status_code == 200
        file_id = response.json()["file_id"]
        
        # 2. Poll
        data = poll_status(client, file_id)
        assert data["status"] == "completed"
        assert os.path.exists(data["docx_path"])
        
        # 3. Verify Email Mock
        mock_email.assert_called_once()
        args, kwargs = mock_email.call_args
        assert kwargs["recipient_email"] == "test@user.com"
        assert os.path.exists(kwargs["attachment_path"])

        # 4. Deep DOCX Verification
        doc = Document(data["docx_path"])
        full_doc_text = "\n".join([p.text for p in doc.paragraphs])
        assert f"Format: {ext}" in full_doc_text
        assert f"Provider: {provider}" in full_doc_text
        assert "OK" in full_doc_text  # Verification report

@pytest.mark.no_mock
@pytest.mark.parametrize("provider", ["local", "yandex"])
def test_e2e_pdf_flow(client, provider):
    """Special case for PDF with provider check."""
    with patch("main.get_provider") as mock_get_provider, \
         patch("main.normalize_file") as mock_norm, \
         patch("main.send_email") as mock_email:
        
        mock_norm.return_value = {"type": "text", "content": "PDF extracted text."}
        mock_provider = MagicMock()
        mock_provider.name = f"mock-{provider}"
        mock_provider.create_protocol = AsyncMock(return_value={"text": "PDF protocol", "latency_ms": 1, "input_tokens": 1, "output_tokens": 1, "messages": []})
        mock_provider.verify_protocol = AsyncMock(return_value={"verification_report": "OK", "input_tokens": 10, "output_tokens": 10, "scores": {"completeness": 5, "accuracy": 5, "hallucinations": 5}})
        mock_provider.format_transcript_with_ai = AsyncMock(return_value={"formatted_text": "fmt"})
        mock_get_provider.return_value = mock_provider
        
        response = client.post("/process-meeting", 
                               files={"file": ("test.pdf", b"%PDF-1.4...", "application/pdf")},
                               data={"provider": provider, "email": "pdf-test@user.com"})
        assert response.status_code == 200
        file_id = response.json()["file_id"]
        
        data = poll_status(client, file_id)
        assert data["status"] == "completed"
        mock_email.assert_called_once()
