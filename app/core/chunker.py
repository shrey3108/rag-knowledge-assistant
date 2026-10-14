from typing import List
from pydantic import BaseModel
from app.core.document_parser import ParsedDocument


class DocumentChunk(BaseModel):
    chunk_id: str
    document_name: str
    page_number: int
    chunk_index: int
    text: str
    char_count: int
    file_hash: str = ""


class RecursiveChunker:
    """Recursively splits document text into semantic chunks with overlap and metadata."""

    SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""]

    def __init__(self, chunk_size: int = 650, chunk_overlap: int = 100):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc: ParsedDocument) -> List[DocumentChunk]:
        """Split a parsed document into structured chunks with page and document metadata."""
        chunks: List[DocumentChunk] = []
        global_chunk_idx = 0
        file_hash = getattr(doc, "file_hash", "")

        for page in doc.pages:
            text = page.text.strip()
            if not text:
                continue

            raw_chunks = self._split_text(text, self.chunk_size, self.chunk_overlap)
            for raw_chunk in raw_chunks:
                clean_chunk = raw_chunk.strip()
                if not clean_chunk:
                    continue
                global_chunk_idx += 1
                chunk_id = f"{doc.filename}_p{page.page_number}_c{global_chunk_idx}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_name=doc.filename,
                        page_number=page.page_number,
                        chunk_index=global_chunk_idx,
                        text=clean_chunk,
                        char_count=len(clean_chunk),
                        file_hash=file_hash,
                    )
                )


        return chunks

    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Recursive splitting implementation."""
        if len(text) <= chunk_size:
            return [text]

        return self._recursive_split(text, chunk_size, chunk_overlap, self.SEPARATORS)

    def _recursive_split(
        self, text: str, chunk_size: int, chunk_overlap: int, separators: List[str]
    ) -> List[str]:
        final_chunks: List[str] = []

        # Find best separator
        separator = separators[-1]
        for sep in separators:
            if sep == "":
                separator = ""
                break
            if sep in text:
                separator = sep
                break

        # Split on the chosen separator
        splits = text.split(separator) if separator != "" else list(text)

        # Merge splits up to chunk_size with overlap
        current_chunk: List[str] = []
        current_length = 0

        for s in splits:
            item_length = len(s) + (len(separator) if current_chunk and separator != "" else 0)

            if current_length + item_length <= chunk_size:
                current_chunk.append(s)
                current_length += item_length
            else:
                if current_chunk:
                    joined = separator.join(current_chunk)
                    final_chunks.append(joined)

                    # Build overlap window for next chunk
                    overlap_items: List[str] = []
                    overlap_len = 0
                    for prev_item in reversed(current_chunk):
                        added_len = len(prev_item) + (len(separator) if overlap_items else 0)
                        if overlap_len + added_len <= chunk_overlap:
                            overlap_items.insert(0, prev_item)
                            overlap_len += added_len
                        else:
                            break
                    current_chunk = overlap_items
                    current_length = overlap_len

                # If single split item itself exceeds chunk_size, recurse on it with finer separators
                if len(s) > chunk_size:
                    sub_separators = separators[separators.index(separator) + 1 :] if separator in separators else []
                    if sub_separators:
                        sub_chunks = self._recursive_split(s, chunk_size, chunk_overlap, sub_separators)
                        final_chunks.extend(sub_chunks)
                    else:
                        # Fallback: slice directly
                        for i in range(0, len(s), chunk_size - chunk_overlap):
                            final_chunks.append(s[i : i + chunk_size])
                else:
                    current_chunk.append(s)
                    current_length += len(s) + (len(separator) if len(current_chunk) > 1 else 0)

        if current_chunk:
            final_chunks.append(separator.join(current_chunk))

        return final_chunks
