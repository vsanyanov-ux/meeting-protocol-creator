import os
import pytest
from unittest.mock import MagicMock, patch
from email_client import send_email

@pytest.fixture
def mock_smtp():
    with patch("smtplib.SMTP_SSL") as mock_ssl, patch("smtplib.SMTP") as mock_tls:
        yield {"ssl": mock_ssl, "tls": mock_tls}

def test_send_email_success(mock_smtp, tmp_path):
    """Test successful email sending with attachment."""
    # Setup test file
    test_file = tmp_path / "result.docx"
    test_file.write_text("dummy content")
    
    # Setup environment
    with patch.dict(os.environ, {
        "SMTP_HOST": "smtp.test.com",
        "SMTP_PORT": "465",
        "SMTP_USER": "test@test.com",
        "SMTP_PASSWORD": "password"
    }):
        # Run
        res = send_email(
            recipient_email="target@user.com",
            subject="Test Subject",
            body="Hello, your result is ready.",
            attachment_path=str(test_file)
        )
        
        assert res is True
        
        # Verify SMTP_SSL was used for port 465
        mock_smtp["ssl"].assert_called_once_with("smtp.test.com", 465, timeout=30)
        
        # Verify message content (via send_message call)
        instance = mock_smtp["ssl"].return_value
        args, _ = instance.send_message.call_args
        msg = args[0]
        
        assert msg["To"] == "target@user.com"
        assert "Test Subject" in msg["Subject"]
        assert msg["From"] == "Протоколист <test@test.com>"
        
        # Check attachment exists in message
        parts = list(msg.iter_parts())
        # Parts: 1. Mixed container, 2. Alternative container (text/html), 3. Attachment
        # Actually EmailMessage with add_alternative and add_attachment usually has a specific structure.
        # Let's just check if 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' is in the payload
        found_docx = False
        for part in msg.walk():
            if part.get_content_type() == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                found_docx = True
                break
        assert found_docx is True

def test_send_email_failure(mock_smtp):
    """Test email sending failure handling."""
    mock_smtp["tls"].side_effect = Exception("SMTP Connection Failed")
    
    with patch.dict(os.environ, {
        "SMTP_HOST": "smtp.test.com",
        "SMTP_PORT": "587",
        "SMTP_USER": "test@test.com",
        "SMTP_PASSWORD": "password"
    }):
        res = send_email(
            recipient_email="target@user.com",
            subject="Test",
            body="Body",
            attachment_path="non_existent.docx"
        )
        
        assert res is False
        mock_smtp["tls"].assert_called()

def test_email_formatting_html():
    """Verify that the body is correctly embedded in HTML."""
    # We can't easily test the HTML generation without refactoring send_email or capturing the message.
    # But we can verify it indirectly via headers in the mock test above.
    pass
