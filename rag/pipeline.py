from .vector_store import query, count
from .llm import generate, is_available


def is_index_populated() -> bool:
    return count() > 0


def retrieve(question: str, n_chunks: int = 5) -> list[dict]:
    """
    Run only the retrieval step — embed the question and return the top-N chunks.

    Each chunk dict has keys: text, metadata, score.
    Useful for debugging retrieval quality and for the evaluator.
    """
    return query(question, n_results=n_chunks)


def _build_prompt(question: str, chunks: list[dict], user_context: str) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk["metadata"].get("source", "unknown")
        context_parts.append(f"[Source {i} — {source}]:\n{chunk['text']}")

    context_block = "\n\n---\n\n".join(context_parts)

    user_ctx_block = (
        f"\n\nUser's current pet data:\n{user_context}" if user_context else ""
    )

    return f"""You are PawPal Assistant, a helpful AI for the PawPal+ pet care scheduling app.
Use only the provided context to answer the user's question accurately and helpfully.
If the context does not contain enough information to answer, say so honestly.
Keep your answer concise, friendly, and practical.
When discussing doctor availability or appointment booking, quote exact days, hours, and fees from the context.

Context:
{context_block}{user_ctx_block}

User question: {question}

Answer:"""


def ask(question: str, user_context: str = "", n_chunks: int = 5) -> dict:
    """
    Run the full RAG pipeline.

    Returns a dict with keys:
        answer      — str: the generated (or fallback) answer
        sources     — list[dict]: retrieved chunks with metadata and score
        llm_used    — bool: True if Ollama generated the answer
    """
    chunks = query(question, n_results=n_chunks)

    if is_available():
        prompt = _build_prompt(question, chunks, user_context)
        response = generate(prompt)
        if response is not None:
            return {"answer": response, "sources": chunks, "llm_used": True}

    # Fallback: surface retrieved chunks directly when Ollama is down
    if not chunks:
        fallback = (
            "I couldn't find relevant information in the knowledge base. "
            "Please try rephrasing your question."
        )
    else:
        lines = ["**Ollama is not running — showing raw knowledge base results:**\n"]
        for i, chunk in enumerate(chunks[:3], 1):
            source = chunk["metadata"].get("source", "unknown")
            snippet = chunk["text"][:500].rstrip()
            lines.append(f"**[{i}] {source}**\n{snippet}…\n")
        fallback = "\n".join(lines)

    return {"answer": fallback, "sources": chunks, "llm_used": False}
