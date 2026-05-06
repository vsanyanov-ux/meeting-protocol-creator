import sys
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import app, status_manager

client = TestClient(app)

def test_verify_email_flag_parsing():
    print("Testing email flag parsing...")
    
    # Mock background tasks to avoid running the full pipeline
    with patch("main.BackgroundTasks.add_task") as mock_add_task:
        # 1. Test with send_email=false
        files = {"file": ("test.mp3", b"fake-mp3-content", "audio/mpeg")}
        data = {"send_email": "false"}
        headers = {"X-App-Password": os.getenv("APP_PASSWORD", "")}
        
        response = client.post("/process-meeting", data=data, files=files, headers=headers)
        assert response.status_code == 200
        
        # Check if should_send_email passed to background task is False
        args, kwargs = mock_add_task.call_args
        # run_full_pipeline(local_path, file_id, metadata, email, provider, force_cpu, session_id, should_send_email)
        # The 8th argument (index 7) should be False
        should_send_email = args[8] # args[0] is run_full_pipeline, so args[1] is local_path... args[8] is should_send_email
        print(f"Passed should_send_email (False case): {should_send_email}")
        assert should_send_email is False
        
        # 2. Test with send_email=true
        mock_add_task.reset_mock()
        data = {"send_email": "true"}
        response = client.post("/process-meeting", data=data, files=files, headers=headers)
        assert response.status_code == 200
        args, kwargs = mock_add_task.call_args
        should_send_email = args[8]
        print(f"Passed should_send_email (True case): {should_send_email}")
        assert should_send_email is True

        # 3. Test with missing send_email (should default to True)
        mock_add_task.reset_mock()
        response = client.post("/process-meeting", files=files, headers=headers)
        assert response.status_code == 200
        args, kwargs = mock_add_task.call_args
        should_send_email = args[8]
        print(f"Passed should_send_email (Default case): {should_send_email}")
        assert should_send_email is True

    print("SUCCESS: Email flag parsing and passing verified!")

if __name__ == "__main__":
    test_verify_email_flag_parsing()
