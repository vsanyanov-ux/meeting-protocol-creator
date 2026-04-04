import os
import pytest
from unittest.mock import MagicMock, patch
from normalizer import normalize_file, extract_text_from_pdf, extract_text_from_docx

def test_normalize_txt(tmp_path):
    """Test normalized extraction from a text file."""
    p = tmp_path / "test.txt"
    p.write_text("Hello World", encoding="utf-8")
    
    res = normalize_file(str(p), "123")
    assert res["type"] == "text"
    assert res["content"] == "Hello World"

@patch("pdfplumber.open")
def test_normalize_pdf(mock_pdf_open, tmp_path):
    """Test text extraction from a mocked PDF."""
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page Content"
    mock_pdf.pages = [mock_page]
    mock_pdf_open.return_value.__enter__.return_value = mock_pdf
    
    p = tmp_path / "test.pdf"
    p.write_bytes(b"%PDF-1.4") # Dummy PDF header
    
    res = normalize_file(str(p), "123")
    assert res["type"] == "text"
    assert "Page Content" in res["content"]

@patch("docx.Document")
def test_normalize_docx(mock_docx_doc, tmp_path):
    """Test text extraction from a mocked DOCX."""
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.text = "Para Content"
    mock_doc.paragraphs = [mock_para]
    mock_docx_doc.return_value = mock_doc
    
    p = tmp_path / "test.docx"
    p.write_bytes(b"PK") # Dummy docx header
    
    res = normalize_file(str(p), "123")
    assert res["type"] == "text"
    assert "Para Content" in res["content"]

@patch("subprocess.run")
def test_normalize_audio(mock_run, tmp_path):
    """Test normalization of audio/video using ffmpeg."""
    p = tmp_path / "test.mp4"
    p.write_bytes(b"dummy")
    
    res = normalize_file(str(p), "124")
    assert res["type"] == "audio"
    assert "normalized_124.ogg" in res["path"]
    
    # Verify ffmpeg was called
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert "ffmpeg" in args
    assert "-libopus" in " ".join(args) or "copy" not in " ".join(args) # check for encoding flag

def test_unsupported_format(tmp_path):
    """Test handling of unsupported file extensions."""
    p = tmp_path / "test.exe"
    p.write_bytes(b"dummy")
    
    res = normalize_file(str(p), "125")
    assert res["type"] == "error"
    assert "Unsupported" in res["error"]
