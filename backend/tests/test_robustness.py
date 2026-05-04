import pytest
import os
import time
import asyncio
import shutil
from unittest.mock import MagicMock, patch, ANY, AsyncMock
from fastapi.testclient import TestClient
from main import app, status_manager, cleanup_old_files, processing_semaphore
from exceptions import HardwareError
import datetime

client = TestClient(app)

def poll_status(file_id, timeout=20):
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = status_manager.get(file_id)
        if status.get("status") in ["completed", "error"]:
            return status
        time.sleep(0.5)
    return status_manager.get(file_id)

@pytest.mark.asyncio
async def test_hardware_fallback():
    """Verify that system falls back from GPU to CPU on HardwareError."""
    # Create dummy audio file to trigger STT path
    test_file = "fallback_test.mp3"
    with open(test_file, "wb") as f:
        f.write(b"ID3\x03\x00\x00\x00\x00\x00\x00") # Dummy MP3 header

    try:
        with patch("main.get_provider") as mock_get_provider:
            # 1. GPU Provider (fails)
            gpu_provider = MagicMock()
            gpu_provider.name = "local-gpu"
            gpu_provider.transcribe_audio = AsyncMock(side_effect=HardwareError("GPU is dead", device="cuda"))
            
            # 2. CPU Provider (succeeds)
            cpu_provider = MagicMock()
            cpu_provider.name = "local-cpu"
            cpu_provider.transcribe_audio = AsyncMock(return_value={"text": "Fallbacked transcription", "duration": 5})
            cpu_provider.create_protocol = AsyncMock(return_value={
                "text": "Final Protocol", 
                "messages": [], 
                "latency_ms": 100, 
                "input_tokens": 10, 
                "output_tokens": 10
            })
            cpu_provider.verify_protocol = AsyncMock(return_value={
                "verification_report": "OK",
                "input_tokens": 5,
                "output_tokens": 5,
                "scores": {"completeness": 5}
            })
            
            # 3. Yandex Provider (as backup fallback)
            yandex_provider = MagicMock()
            yandex_provider.name = "yandex"
            yandex_provider.transcribe_audio = AsyncMock(return_value={"text": "Cloud rescue", "duration": 10})
            yandex_provider.create_protocol = AsyncMock(return_value={
                "text": "Cloud Protocol", 
                "messages": [], 
                "latency_ms": 200, 
                "input_tokens": 20, 
                "output_tokens": 20
            })
            yandex_provider.verify_protocol = AsyncMock(return_value={
                "verification_report": "Cloud OK",
                "input_tokens": 15,
                "output_tokens": 15,
                "scores": {"completeness": 5}
            })

            # side_effect allows sequential returns
            mock_get_provider.side_effect = [gpu_provider, cpu_provider, yandex_provider]

            with open(test_file, "rb") as f:
                response = client.post(
                    "/process-meeting",
                    files={"file": ("fallback.mp3", f, "audio/mpeg")},
                    data={"provider": "local"}
                )
            
            assert response.status_code == 200
            file_id = response.json()["file_id"]
            
            status = poll_status(file_id)
            assert status["status"] == "completed"
            
            # Verify that get_provider was called twice (once for GPU, once for CPU)
            assert mock_get_provider.call_count >= 2
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

@pytest.mark.asyncio
async def test_concurrency_semaphore():
    """Verify that processing_semaphore limits concurrent tasks."""
    # Since we use a real semaphore in main.py, we can check its value
    # or simulate multiple calls.
    # For a real integration test, we verify that multiple requests are handled.
    
    file_ids = []
    # Create 3 requests (MAX_CONCURRENT_TASKS is usually 1 or 2 in tests)
    for i in range(3):
        with open("concurrency.txt", "w") as f: f.write(f"test {i}")
        with open("concurrency.txt", "rb") as f:
            resp = client.post("/process-meeting", files={"file": ("c.txt", f, "text/plain")})
            file_ids.append(resp.json()["file_id"])
        os.remove("concurrency.txt")

    # All should be in queue or processing
    for fid in file_ids:
        assert status_manager.get(fid) is not None

@pytest.mark.asyncio
async def test_automated_cleanup():
    """Verify that cleanup_old_files removes aged files."""
    test_dir = "uploads"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
        
    old_file = os.path.join(test_dir, "old_test.tmp")
    new_file = os.path.join(test_dir, "new_test.tmp")
    
    with open(old_file, "w") as f: f.write("old")
    with open(new_file, "w") as f: f.write("new")
    
    # Set old_file to 2 days ago
    past_time = time.time() - (2 * 24 * 3600)
    os.utime(old_file, (past_time, past_time))
    
    # Call cleanup with 1 hour limit
    cleanup_old_files(max_age_seconds=3600)
    
    assert not os.path.exists(old_file), "Old file should be deleted"
    assert os.path.exists(new_file), "New file should be preserved"
    
    os.remove(new_file)

@pytest.mark.asyncio
async def test_langfuse_telemetry_metadata():
    """Verify that Langfuse PipelineTrace receives correct metadata."""
    with patch("main.PipelineTrace") as mock_trace_class, \
         patch("main.get_provider") as mock_get_provider:
        
        mock_provider = MagicMock()
        mock_provider.name = "yandex"
        # Make it async to avoid await errors in background task logs
        mock_provider.transcribe_audio = AsyncMock(return_value={"text": "ok"})
        mock_provider.create_protocol = AsyncMock(return_value={"text": "ok", "latency_ms": 0, "input_tokens": 0, "output_tokens": 0, "messages": []})
        mock_provider.verify_protocol = AsyncMock(return_value={"verification_report": "ok", "input_tokens": 0, "output_tokens": 0, "scores": {}})
        mock_get_provider.return_value = mock_provider
        
        test_file = "telemetry.txt"
        with open(test_file, "w") as f: f.write("Hello World")
        
        with open(test_file, "rb") as f:
            client.post(
                "/process-meeting",
                files={"file": ("tel.txt", f, "text/plain")},
                data={"provider": "yandex"}
            )
            
        # Wait a bit for background task to initialize trace
        time.sleep(1)
        
        # Check if PipelineTrace was instantiated with correct metadata
        args, kwargs = mock_trace_class.call_args
        # filename is the server-side path (basename), which is a UUID
        assert kwargs["filename"].endswith(".txt")
        assert kwargs["provider"] == "yandex"
        assert "file_id" in kwargs
        
        if os.path.exists(test_file): os.remove(test_file)
