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
