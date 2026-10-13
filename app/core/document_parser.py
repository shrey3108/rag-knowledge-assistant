import io
import re
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
import pypdf


class ParsedPage(BaseModel):
    page_number: int
    text: str


class ParsedDocument(BaseModel):
    filename: str
    file_type: str
    total_pages: int
    pages: List[ParsedPage]

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text)


class DocumentParser:
    """Parses PDF, TXT, and Markdown documents into structured pages with cleaned text."""

    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}

    @classmethod
    def clean_text(cls, text: str) -> str:
        """Normalize line breaks, remove null bytes and excessive whitespace."""
        if not text:
            return ""
        # Remove null characters
        text = text.replace("\x00", "")
        # Normalize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Strip trailing/leading spaces on each line and collapse internal whitespace
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        text = "\n".join(lines)
        # Replace 3 or more newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


    @classmethod
    def parse_bytes(cls, content: bytes, filename: str) -> ParsedDocument:
        """Parse raw file bytes into a ParsedDocument."""
        ext = Path(filename).suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{ext}'. Supported formats: {', '.join(cls.SUPPORTED_EXTENSIONS)}"
            )

        if ext == ".pdf":
            return cls._parse_pdf(content, filename)
        else:
            return cls._parse_text(content, filename, ext)

    @classmethod
    def parse_file(cls, file_path: str | Path) -> ParsedDocument:
        """Parse a file from disk."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")
        content = path.read_bytes()
        return cls.parse_bytes(content, path.name)

    @classmethod
    def _parse_pdf(cls, content: bytes, filename: str) -> ParsedDocument:
        stream = io.BytesIO(content)
        reader = pypdf.PdfReader(stream)
        pages: List[ParsedPage] = []

        total_pages = len(reader.pages)
        for idx, page in enumerate(reader.pages, start=1):
            try:
                extracted = page.extract_text() or ""
            except Exception:
                extracted = ""
            cleaned = cls.clean_text(extracted)
            if cleaned:
                pages.append(ParsedPage(page_number=idx, text=cleaned))

        if not pages:
            # Document has no extractable text (e.g. scanned image or blank)
            pages.append(ParsedPage(page_number=1, text=""))

        return ParsedDocument(
            filename=filename,
            file_type="pdf",
            total_pages=total_pages,
            pages=pages,
        )

    @classmethod
    def _parse_text(cls, content: bytes, filename: str, ext: str) -> ParsedDocument:
        # Decode trying UTF-8 first, then fallback to latin-1
        try:
            raw_text = content.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = content.decode("latin-1", errors="replace")

        cleaned = cls.clean_text(raw_text)
        file_type = "markdown" if ext in {".md", ".markdown"} else "text"

        return ParsedDocument(
            filename=filename,
            file_type=file_type,
            total_pages=1,
            pages=[ParsedPage(page_number=1, text=cleaned)],
        )
