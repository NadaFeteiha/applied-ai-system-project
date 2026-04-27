"""
Retrieval quality evaluator for the RAG pipeline.

Measures how well the vector store retrieves relevant chunks for a set of
reference questions. Two complementary metrics are reported:

  keyword_coverage   — fraction of expected keywords found in the top-N chunks
                       (tests whether the *right content* was retrieved)

  avg_similarity     — mean cosine-similarity score of the retrieved chunks
                       (tests how *semantically close* the chunks are to the query)

Usage
-----
    from rag.evaluator import run_eval_suite, evaluate_question

    # Run the full built-in test suite
    results = run_eval_suite()
    print(f"Coverage: {results['avg_keyword_coverage']:.0%}")
    print(f"Similarity: {results['avg_similarity_score']:.0%}")

    # Evaluate a single custom question
    r = evaluate_question("how often feed my dog", ["twice", "morning", "evening"])
    print(r)
"""

from .vector_store import query

# ── Reference eval suite ─────────────────────────────────────────────────────
# Each entry: (question, [expected_keywords_in_retrieved_chunks])
# Keywords are lowercase; matching is case-insensitive substring search.

EVAL_SUITE: list[tuple[str, list[str]]] = [
    (
        "How often should I feed my dog?",
        ["twice", "morning", "evening", "puppy", "portion"],
    ),
    (
        "What vaccines does my cat need?",
        ["vaccine", "vaccination", "rabies", "feline", "booster"],
    ),
    (
        "How do I groom a rabbit?",
        ["brush", "groom", "nail", "fur", "coat"],
    ),
    (
        "What fish need in their tank?",
        ["water", "tank", "temperature", "filter", "aquarium"],
    ),
    (
        "What should birds eat?",
        ["seed", "pellet", "fruit", "vegetable", "fresh"],
    ),
    (
        "Dr. Sarah Chen availability and fees",
        ["monday", "saturday", "sunday", "closed", "85"],
    ),
    (
        "Which vet handles emergency appointments?",
        ["emergency", "urgent", "same-day", "contact", "call"],
    ),
    (
        "How much exercise does a dog need daily?",
        ["exercise", "walk", "minutes", "daily", "breed"],
    ),
]


# ── Scoring helpers ───────────────────────────────────────────────────────────

def keyword_coverage(chunks: list[dict], expected_keywords: list[str]) -> float:
    """
    Fraction of expected_keywords found (case-insensitive) across all chunks.
    Returns 0.0 if chunks or keywords are empty.
    """
    if not chunks or not expected_keywords:
        return 0.0
    combined = " ".join(c["text"] for c in chunks).lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in combined)
    return round(hits / len(expected_keywords), 3)


def avg_similarity_score(chunks: list[dict]) -> float:
    """
    Mean cosine-similarity score across retrieved chunks (0.0 – 1.0).
    Returns 0.0 if chunks is empty.
    """
    if not chunks:
        return 0.0
    return round(sum(c["score"] for c in chunks) / len(chunks), 3)


# ── Per-question evaluation ───────────────────────────────────────────────────

def evaluate_question(
    question: str,
    expected_keywords: list[str],
    n_results: int = 5,
) -> dict:
    """
    Retrieve chunks for *question* and score them.

    Returns a dict with keys:
        question            — the input question
        chunks_retrieved    — how many chunks were returned
        keyword_coverage    — float 0–1
        avg_similarity      — float 0–1
        sources             — list of source names that were retrieved
    """
    chunks = query(question, n_results=n_results)
    return {
        "question": question,
        "chunks_retrieved": len(chunks),
        "keyword_coverage": keyword_coverage(chunks, expected_keywords),
        "avg_similarity": avg_similarity_score(chunks),
        "sources": list({c["metadata"].get("source", "unknown") for c in chunks}),
    }


# ── Full eval suite ───────────────────────────────────────────────────────────

def run_eval_suite(n_results: int = 5) -> dict:
    """
    Run every question in EVAL_SUITE and aggregate the scores.

    Returns a dict with keys:
        questions_evaluated     — int
        avg_keyword_coverage    — float 0–1  (higher = better content recall)
        avg_similarity_score    — float 0–1  (higher = better semantic match)
        per_question            — list[dict] from evaluate_question()
    """
    results = [
        evaluate_question(q, kws, n_results) for q, kws in EVAL_SUITE
    ]
    return {
        "questions_evaluated": len(results),
        "avg_keyword_coverage": round(
            sum(r["keyword_coverage"] for r in results) / len(results), 3
        ),
        "avg_similarity_score": round(
            sum(r["avg_similarity"] for r in results) / len(results), 3
        ),
        "per_question": results,
    }
