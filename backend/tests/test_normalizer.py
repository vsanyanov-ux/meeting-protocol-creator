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
    # Proper ZIP/DOCX header
    p.write_bytes(b"PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00\x21\x00")
    
    # We need to mock magic because on some systems it still won't identify tiny ZIPs as DOCX
    with patch("magic.from_file", return_value="application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        res = normalize_file(str(p), "123")
        assert res["type"] == "text"
        assert "Para Content" in res["content"]

@patch("subprocess.run")
def test_normalize_audio(mock_run, tmp_path):
    """Test normalization of audio/video using ffmpeg."""
    p = tmp_path / "test.mp4"
    # Minimal MP4-like content or just mock magic
    p.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00")
    
    with patch("magic.from_file", return_value="video/mp4"):
        mock_run.return_value.returncode = 0
        res = normalize_file(str(p), "124")
        assert res["type"] == "audio"
        assert "normalized_124.ogg" in res["path"]

def test_unsupported_format(tmp_path):
    """Test handling of unsupported file extensions."""
    p = tmp_path / "test.exe"
    p.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff")
    
    with patch("magic.from_file", return_value="application/x-msdownload"):
        res = normalize_file(str(p), "125")
        assert res["type"] == "error"
        assert "Не удалось распознать" in res["error"]
