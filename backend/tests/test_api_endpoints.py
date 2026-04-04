import pytest
from unittest.mock import patch, MagicMock
import os
import uuid

def test_root(client):
    """Simple root check."""
    response = client.get("/")
    assert response.status_code == 200
    assert "running" in response.json()["message"]

def test_process_meeting_invalid_extension(client):
    """Verify backend rejects unsupported extensions."""
    files = {"file": ("test.exe", b"dummy", "application/octet-stream")}
    response = client.post("/process-meeting", files=files)
    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]

def test_process_meeting_success(client):
    """Verify valid file upload and task ID generation."""
    files = {"file": ("test.mp3", b"fake-mp3-content", "audio/mpeg")}
    response = client.post("/process-meeting", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processing"
    assert "file_id" in data

def test_get_status_not_found(client):
    """Verify 404 for unknown task IDs."""
    response = client.get("/status/unknown-id")
    assert response.status_code == 404

def test_api_workflow(client):
    """Full API workflow test with mocks."""
    # 1. Upload
    files = {"file": ("meeting.wav", b"wav-content", "audio/wav")}
    response = client.post("/process-meeting", files=files)
    file_id = response.json()["file_id"]
    
    # 2. Check initial status
    status_resp = client.get(f"/status/{file_id}")
    assert status_resp.status_code == 200
    assert "status" in status_resp.json()
    
    # 3. Simulate completion (Manually update the dict for integration test)
    from main import processing_status
    dummy_docx = "temp_protocols/mock_protocol.docx"
    processing_status[file_id] = {
        "status": "completed",
        "message": "Protocol ready.",
        "docx_path": dummy_docx
    }
    
    # Check completed status
    status_resp = client.get(f"/status/{file_id}")
    assert status_resp.json()["status"] == "completed"
    
    # 4. Download (Create dummy file to satisfy FileResponse)
    with open(dummy_docx, "wb") as f:
        f.write(b"dummy docx content")
    
    try:
        dl_resp = client.get(f"/download/{file_id}")
        assert dl_resp.status_code == 200
        assert dl_resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    finally:
        if os.path.exists(dummy_docx):
            os.remove(dummy_docx)

def test_feedback_success(client):
    """Verify feedback submission."""
    file_id = str(uuid.uuid4())
    # Mock existence in processing_status
    from main import processing_status
    processing_status[file_id] = {"status": "completed"}
    
    response = client.post(f"/feedback/{file_id}", json={
        "score": 5.0,
        "comment": "Excellent quality!",
        "score_name": "user_rating"
    })
    assert response.status_code == 200
    assert response.json()["status"] in ["ok", "skipped"]
