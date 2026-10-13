import pytest
from pathlib import Path
from app.core.document_parser import DocumentParser, ParsedDocument


def test_clean_text():
    raw = "  Hello \r\n\r\n\r\n world \x00 with   tabs\tand spaces.  "
    cleaned = DocumentParser.clean_text(raw)
    assert "\x00" not in cleaned
    assert "\r" not in cleaned
    assert "  " not in cleaned
    assert cleaned == "Hello\n\nworld with tabs and spaces."


def test_parse_markdown_file(sample_docs_dir: Path):
    md_file = sample_docs_dir / "ai_ethics_framework.md"
    assert md_file.exists()
    doc = DocumentParser.parse_file(md_file)
    assert isinstance(doc, ParsedDocument)
    assert doc.filename == "ai_ethics_framework.md"
    assert doc.file_type == "markdown"
    assert doc.total_pages == 1
    assert "Algorithmic Fairness" in doc.full_text


def test_parse_text_file(sample_docs_dir: Path):
    txt_file = sample_docs_dir / "cloud_infrastructure_guide.txt"
    assert txt_file.exists()
    doc = DocumentParser.parse_file(txt_file)
    assert isinstance(doc, ParsedDocument)
    assert doc.filename == "cloud_infrastructure_guide.txt"
    assert doc.file_type == "text"
    assert "ZERO TRUST ARCHITECTURE" in doc.full_text


def test_parse_pdf_file(sample_docs_dir: Path):
    pdf_file = sample_docs_dir / "enterprise_security_policy.pdf"
    assert pdf_file.exists()
    doc = DocumentParser.parse_file(pdf_file)
    assert isinstance(doc, ParsedDocument)
    assert doc.filename == "enterprise_security_policy.pdf"
    assert doc.file_type == "pdf"
    assert doc.total_pages >= 2
    assert "ENCRYPTION" in doc.full_text.upper()


def test_unsupported_extension():
    with pytest.raises(ValueError) as exc:
        DocumentParser.parse_bytes(b"some content", "data.docx")
    assert "Unsupported file format" in str(exc.value)


def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        DocumentParser.parse_file("non_existent_file.pdf")
