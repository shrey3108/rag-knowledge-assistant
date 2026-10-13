import pytest
from app.core.chunker import RecursiveChunker, DocumentChunk
from app.core.document_parser import ParsedDocument, ParsedPage


def test_chunker_overlap_validation():
    with pytest.raises(ValueError):
        RecursiveChunker(chunk_size=100, chunk_overlap=100)


def test_chunking_short_document():
    doc = ParsedDocument(
        filename="short_test.txt",
        file_type="text",
        total_pages=1,
        pages=[ParsedPage(page_number=1, text="This is a short single sentence.")],
    )
    chunker = RecursiveChunker(chunk_size=500, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].document_name == "short_test.txt"
    assert chunks[0].page_number == 1
    assert chunks[0].text == "This is a short single sentence."
    assert chunks[0].chunk_id == "short_test.txt_p1_c1"


def test_chunking_long_document_with_overlap():
    paragraph = "Paragraph one with detailed statements about software reliability. " * 8
    doc = ParsedDocument(
        filename="long_test.txt",
        file_type="text",
        total_pages=1,
        pages=[ParsedPage(page_number=1, text=paragraph)],
    )
    chunker = RecursiveChunker(chunk_size=200, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) > 1
    for c in chunks:
        assert isinstance(c, DocumentChunk)
        assert c.document_name == "long_test.txt"
        assert len(c.text) > 0


def test_chunking_multi_page_document():
    doc = ParsedDocument(
        filename="multipage.pdf",
        file_type="pdf",
        total_pages=2,
        pages=[
            ParsedPage(page_number=1, text="Page 1 content discussing architecture."),
            ParsedPage(page_number=2, text="Page 2 content discussing security policies."),
        ],
    )
    chunker = RecursiveChunker(chunk_size=300, chunk_overlap=50)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert "Page 1" in chunks[0].text
    assert "Page 2" in chunks[1].text
