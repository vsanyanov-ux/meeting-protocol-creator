import pytest
from fastapi.testclient import TestClient
import os
from unittest.mock import patch

# IMPORTANT: We need to reload the app or at least the environment variables
# since main.py reads them at module level or during middleware execution.
# Fortunately, os.getenv() in middleware is called per request.

@pytest.fixture
def auth_client():
    from main import app
    with TestClient(app) as c:
        yield c

def test_public_endpoints(auth_client):
    """Verify that /, /health, and /favicon.ico remain public."""
    # Ensure no password in env for this test part (though middleware handles it)
    with patch.dict(os.environ, {"APP_PASSWORD": "protocolist2026"}):
        for path in ["/", "/health"]:
            response = auth_client.get(path)
            assert response.status_code == 200

def test_protected_endpoints_no_auth(auth_client):
    """Verify that /info, /status, etc. are blocked without password."""
    with patch.dict(os.environ, {"APP_PASSWORD": "protocolist2026"}):
        # /info used to be public, now should be protected
        response = auth_client.get("/info")
        assert response.status_code == 401
        
        # /history should also be protected
        response = auth_client.get("/history")
        assert response.status_code == 401

def test_protected_endpoints_with_auth(auth_client):
    """Verify that /info, /status, etc. work with correct password."""
    password = "protocolist2026"
    with patch.dict(os.environ, {"APP_PASSWORD": password}):
        # Test with header
        response = auth_client.get("/info", headers={"X-App-Password": password})
        assert response.status_code == 200
        
        # Test with query param
        response = auth_client.get("/info", params={"password": password})
        assert response.status_code == 200

def test_wrong_password(auth_client):
    """Verify that wrong password is rejected."""
    with patch.dict(os.environ, {"APP_PASSWORD": "protocolist2026"}):
        response = auth_client.get("/info", headers={"X-App-Password": "wrong"})
        assert response.status_code == 401
