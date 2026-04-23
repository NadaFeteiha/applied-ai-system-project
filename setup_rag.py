"""
Run this script once to index the knowledge base into ChromaDB.
Usage:  python setup_rag.py
"""

from pathlib import Path


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 30) -> list[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def build_docs(kb_path: Path) -> list[dict]:
    docs, doc_id = [], 0
    for category in ["pet_care", "doctors"]:
        folder = kb_path / category
        if not folder.exists():
            print(f"  [warn] {folder} not found — skipping.")
            continue
        for file in sorted(folder.glob("*.txt")):
            text = file.read_text(encoding="utf-8")
            source = file.stem.replace("_", " ").title()
            chunks = chunk_text(text)
            for chunk in chunks:
                docs.append(
                    {
                        "id": f"doc_{doc_id}",
                        "text": chunk,
                        "metadata": {
                            "source": source,
                            "category": category,
                            "file": file.name,
                        },
                    }
                )
                doc_id += 1
            print(f"  {file.name:45s}  {len(chunks):3d} chunks")
    return docs


def main():
    print("PawPal+ RAG — indexing knowledge base\n")
    kb_path = Path(__file__).parent / "knowledge_base"

    print("Building document chunks …")
    docs = build_docs(kb_path)
    print(f"\nTotal chunks: {len(docs)}")

    print("\nLoading embedding model and writing to ChromaDB …")
    from rag.vector_store import add_documents, count

    add_documents(docs)
    print(f"\nDone! ChromaDB now contains {count()} indexed chunks.")
    print("\nYou can now run the app:  streamlit run app.py")


if __name__ == "__main__":
    main()
