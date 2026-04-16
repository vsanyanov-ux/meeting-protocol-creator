import os
import pytest
from unittest.mock import MagicMock, patch
from normalizer import normalize_file

@pytest.mark.parametrize("ext, mime", [
    ("mp3", "audio/mpeg"),
    ("wav", "audio/wav"),
    ("m4a", "audio/mp4"),
    ("ogg", "audio/ogg"),
    ("aac", "audio/aac"),
    ("flac", "audio/flac"),
    ("mp4", "video/mp4"),
    ("m4v", "video/x-m4v"),
    ("mov", "video/quicktime"),
    ("avi", "video/x-msvideo"),
    ("webm", "video/webm"),
])
def test_normalize_media_formats(tmp_path, ext, mime):
    """Test that all media formats are correctly routed to FFmpeg."""
    p = tmp_path / f"test.{ext}"
    p.write_bytes(b"dummy content")
    
    with patch("magic.from_file", return_value=mime), \
         patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        
        res = normalize_file(str(p), "123")
        assert res["type"] == "audio"
        assert f"normalized_123.ogg" in res["path"]
        # Verify FFmpeg was called with the right input
        args = mock_run.call_args[0][0]
        assert str(p) in args

@pytest.mark.parametrize("ext, mime, content", [
    ("txt", "text/plain", "Hello World"),
    ("pdf", "application/pdf", "PDF Content"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "DOCX Content"),
    ("doc", "application/msword", "DOC Content"),
])
def test_normalize_document_formats(tmp_path, ext, mime, content):
    """Test that document formats are correctly recognized and parsed."""
    p = tmp_path / f"test.{ext}"
    p.write_bytes(content.encode("utf-8"))
    
    with patch("magic.from_file", return_value=mime), \
         patch("normalizer.extract_text_from_pdf", return_value=content), \
         patch("normalizer.extract_text_from_docx", return_value=content):
        
        res = normalize_file(str(p), "124")
        assert res["type"] == "text"
        assert res["content"] == content

def test_unsupported_format(tmp_path):
    """Verify that truly unsupported formats (e.g. .exe) return an error."""
    p = tmp_path / "test.exe"
    p.write_bytes(b"\xff\xfe\xfd\xfc\x00\x01") # Non-UTF8 binary data
    
    with patch("magic.from_file", return_value="application/x-msdownload"):
        res = normalize_file(str(p), "125")
        assert res["type"] == "error"
        assert "Не удалось распознать" in res["error"]
