"""
Ingest custom documents into the knowledge base at runtime.

Supports .txt and .pdf files (pypdf required for PDF).
Chunks are upserted into ChromaDB under category="custom" so they
participate in all retrieval queries alongside the built-in KB.
"""

import datetime
import tempfile
from pathlib import Path

from .vector_store import add_documents, delete_by_source


# ── Chunking ─────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = 200, overlap: int = 30) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


# ── File readers ──────────────────────────────────────────────────────────────

def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_pdf(path: Path) -> str:
    try:
        import pypdf
    except ImportError:
        raise ImportError(
            "pypdf is required to index PDF files. "
            "Install it with:  pip install pypdf"
        )
    reader = pypdf.PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def _read_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".txt":
        return _read_txt(path)
    raise ValueError(f"Unsupported file type '{ext}'. Use .txt or .pdf")


# ── Doc builders ──────────────────────────────────────────────────────────────

def _build_docs(
    text: str,
    source_name: str,
    filename: str,
    category: str,
    chunk_size: int,
    overlap: int,
) -> list[dict]:
    chunks = _chunk_text(text, chunk_size, overlap)
    timestamp = datetime.datetime.utcnow().isoformat()
    safe_id = source_name.lower().replace(" ", "_").replace("/", "_")
    return [
        {
            "id": f"custom_{safe_id}_{i}",
            "text": chunk,
            "metadata": {
                "source": source_name,
                "category": category,
                "file": filename,
                "source_type": "custom",
                "indexed_at": timestamp,
            },
        }
        for i, chunk in enumerate(chunks)
    ]


# ── Public API ────────────────────────────────────────────────────────────────

def ingest_file(
    path: "Path | str",
    source_name: str | None = None,
    category: str = "custom",
    chunk_size: int = 200,
    overlap: int = 30,
) -> int:
    """
    Read, chunk, and index a single .txt or .pdf file into ChromaDB.

    Args:
        path:        Path to the file.
        source_name: Display name for this source (defaults to file stem).
        category:    Metadata category tag (default "custom").
        chunk_size:  Words per chunk.
        overlap:     Overlapping words between consecutive chunks.

    Returns:
        Number of chunks indexed.
    """
    path = Path(path)
    name = source_name or path.stem.replace("_", " ").title()
    text = _read_file(path)
    docs = _build_docs(text, name, path.name, category, chunk_size, overlap)
    add_documents(docs)
    return len(docs)


def ingest_bytes(
    data: bytes,
    filename: str,
    source_name: str | None = None,
    category: str = "custom",
    chunk_size: int = 200,
    overlap: int = 30,
) -> int:
    """
    Index raw bytes (e.g. from st.file_uploader) without writing a permanent file.

    Writes a short-lived temp file, indexes it, then deletes it.

    Returns:
        Number of chunks indexed.
    """
    suffix = Path(filename).suffix.lower()
    name = source_name or Path(filename).stem.replace("_", " ").title()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        text = _read_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    docs = _build_docs(text, name, filename, category, chunk_size, overlap)
    add_documents(docs)
    return len(docs)


def ingest_text(
    text: str,
    source_name: str,
    category: str = "custom",
    chunk_size: int = 200,
    overlap: int = 30,
) -> int:
    """
    Chunk and index a raw string directly.

    Returns:
        Number of chunks indexed.
    """
    docs = _build_docs(
        text, source_name, f"{source_name}.txt", category, chunk_size, overlap
    )
    add_documents(docs)
    return len(docs)


def remove_source(source_name: str) -> None:
    """Remove every chunk belonging to *source_name* from the vector store."""
    delete_by_source(source_name)
