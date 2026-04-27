import chromadb
from pathlib import Path
from .embedder import embed

_DB_PATH = Path(__file__).parent.parent / "chroma_db"
_COLLECTION_NAME = "pawpal_knowledge"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(_DB_PATH))
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_documents(docs: list[dict]) -> None:
    """Index documents. Each doc must have keys: id, text, metadata (dict)."""
    col = _get_collection()
    col.upsert(
        ids=[d["id"] for d in docs],
        embeddings=embed([d["text"] for d in docs]),
        documents=[d["text"] for d in docs],
        metadatas=[d.get("metadata", {}) for d in docs],
    )


def query(text: str, n_results: int = 5) -> list[dict]:
    """Return top-n chunks most similar to the query text."""
    col = _get_collection()
    count = col.count()
    if count == 0:
        return []
    n_results = min(n_results, count)
    results = col.query(
        query_embeddings=embed([text]),
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    out = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        out.append({"text": doc, "metadata": meta, "score": round(1 - dist, 4)})
    return out


def count() -> int:
    return _get_collection().count()


def list_sources() -> list[dict]:
    """
    Return every unique source with its category, source_type, and chunk count.

    Each entry::

        {
            "source":      "Dogs",
            "category":    "pet_care",
            "source_type": "builtin",   # or "custom"
            "count":       18,
        }
    """
    col = _get_collection()
    if col.count() == 0:
        return []
    results = col.get(include=["metadatas"])
    index: dict[str, dict] = {}
    for meta in results["metadatas"]:
        src = meta.get("source", "unknown")
        if src not in index:
            index[src] = {
                "source": src,
                "category": meta.get("category", "unknown"),
                "source_type": meta.get("source_type", "builtin"),
                "count": 0,
            }
        index[src]["count"] += 1
    return sorted(index.values(), key=lambda x: (x["category"], x["source"]))


def delete_by_source(source_name: str) -> None:
    """Delete all chunks whose metadata.source equals *source_name*."""
    col = _get_collection()
    col.delete(where={"source": source_name})


def count_by_category() -> dict[str, int]:
    """Return a mapping of category → chunk count."""
    col = _get_collection()
    if col.count() == 0:
        return {}
    results = col.get(include=["metadatas"])
    counts: dict[str, int] = {}
    for meta in results["metadatas"]:
        cat = meta.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items()))
