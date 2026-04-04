import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import shutil

# Set dummy environment variables for tests
os.environ["YANDEX_API_KEY"] = "test-api-key"
os.environ["YANDEX_FOLDER_ID"] = "test-folder-id"
os.environ["ALLOWED_ORIGINS"] = "*"
os.environ["AI_PROVIDER"] = "yandex"

from main import app

@pytest.fixture(autouse=True)
def mock_external_services():
    """Globally mock expensive or external services."""
    with patch("main.ai_provider") as mock_provider, \
         patch("main.send_email") as mock_email, \
         patch("main.PipelineTrace") as mock_trace, \
         patch("main.submit_score") as mock_score, \
         patch("main.normalize_file") as mock_norm:
        
        # Setup default mock behaviors
        mock_provider.name = "mock-provider"
        mock_provider.transcribe_audio.return_value = "This is a mock transcription."
        mock_provider.create_protocol.return_value = {
            "text": "## Protocol\nMocked protocol content.",
            "latency_ms": 100,
            "input_tokens": 10,
            "output_tokens": 20,
            "messages": []
        }
        
        mock_email.return_value = True
        mock_norm.return_value = {"type": "audio", "path": "mock_audio.ogg"}
        
        yield {
            "provider": mock_provider,
            "email": mock_email,
            "trace": mock_trace,
            "score": mock_score,
            "norm": mock_norm
        }

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Ensure test directories are clean but exist."""
    dirs = ["uploads", "temp_protocols"]
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
    yield
    # We could cleanup here, but standard app cleanup handles most.
