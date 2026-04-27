"""
Unit and integration tests for rag/evaluator.py.

Unit tests cover the pure helper functions (keyword_coverage, avg_similarity_score)
and require no ChromaDB connection.

Integration tests cover evaluate_question and run_eval_suite and are automatically
skipped when the knowledge base has not been indexed yet (run setup_rag.py first).
"""

import pytest
from rag.evaluator import (
    keyword_coverage,
    avg_similarity_score,
    evaluate_question,
    run_eval_suite,
    EVAL_SUITE,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chunk(text: str, score: float = 0.8) -> dict:
    return {"text": text, "metadata": {"source": "test"}, "score": score}


@pytest.fixture(scope="session")
def kb_available() -> bool:
    try:
        from rag.vector_store import count
        return count() > 0
    except Exception:
        return False


@pytest.fixture
def require_kb(kb_available):
    if not kb_available:
        pytest.skip("Knowledge base not indexed — run: python setup_rag.py")


# ── keyword_coverage — pure function ─────────────────────────────────────────

class TestKeywordCoverage:
    def test_all_keywords_found(self):
        chunks = [_chunk("dogs need feeding twice a day in the morning and evening")]
        assert keyword_coverage(chunks, ["twice", "morning", "evening"]) == 1.0

    def test_no_keywords_found(self):
        chunks = [_chunk("fish swim in tanks")]
        assert keyword_coverage(chunks, ["vaccine", "rabies", "booster"]) == 0.0

    def test_partial_coverage(self):
        chunks = [_chunk("cats need rabies vaccines")]
        result = keyword_coverage(chunks, ["vaccine", "rabies", "booster"])
        assert 0.0 < result < 1.0

    def test_case_insensitive_matching(self):
        chunks = [_chunk("Rabies vaccine is recommended for all dogs.")]
        assert keyword_coverage(chunks, ["rabies", "vaccine"]) == 1.0

    def test_uppercase_keyword_matches_lowercase_text(self):
        chunks = [_chunk("the morning routine includes feeding")]
        assert keyword_coverage(chunks, ["MORNING", "FEEDING"]) == 1.0

    def test_keyword_found_across_multiple_chunks(self):
        chunks = [_chunk("dogs eat in the morning"), _chunk("cats prefer evening feeding")]
        assert keyword_coverage(chunks, ["morning", "evening"]) == 1.0

    def test_empty_chunks_returns_zero(self):
        assert keyword_coverage([], ["vaccine", "rabies"]) == 0.0

    def test_empty_keywords_returns_zero(self):
        chunks = [_chunk("dogs and cats are pets")]
        assert keyword_coverage(chunks, []) == 0.0

    def test_single_keyword_found(self):
        chunks = [_chunk("aquarium fish need clean water")]
        assert keyword_coverage(chunks, ["water"]) == 1.0

    def test_single_keyword_not_found(self):
        chunks = [_chunk("dogs need walks daily")]
        assert keyword_coverage(chunks, ["vaccine"]) == 0.0

    def test_result_rounds_to_3_decimal_places(self):
        chunks = [_chunk("one keyword here")]
        result = keyword_coverage(chunks, ["one", "two", "three"])
        assert result == round(result, 3)

    def test_keyword_found_as_substring_of_longer_word(self):
        # "brush" appears inside "brushing" — substring match should count
        chunks = [_chunk("regular brushing keeps the coat healthy")]
        assert keyword_coverage(chunks, ["brush"]) == 1.0


# ── avg_similarity_score — pure function ─────────────────────────────────────

class TestAvgSimilarityScore:
    def test_single_chunk_exact_score(self):
        assert avg_similarity_score([_chunk("text", score=0.85)]) == 0.85

    def test_average_of_two_chunks(self):
        chunks = [_chunk("a", score=0.6), _chunk("b", score=0.8)]
        assert avg_similarity_score(chunks) == pytest.approx(0.7, abs=0.001)

    def test_average_of_three_chunks(self):
        chunks = [_chunk("a", 0.5), _chunk("b", 0.7), _chunk("c", 0.9)]
        assert avg_similarity_score(chunks) == pytest.approx(0.7, abs=0.001)

    def test_empty_chunks_returns_zero(self):
        assert avg_similarity_score([]) == 0.0

    def test_score_of_zero(self):
        assert avg_similarity_score([_chunk("text", score=0.0)]) == 0.0

    def test_score_of_one(self):
        assert avg_similarity_score([_chunk("text", score=1.0)]) == 1.0

    def test_result_rounds_to_3_decimal_places(self):
        result = avg_similarity_score([_chunk("a", 0.333), _chunk("b", 0.667)])
        assert result == round(result, 3)

    def test_five_chunks_average(self):
        scores = [0.60, 0.70, 0.80, 0.90, 1.00]
        chunks = [_chunk(f"chunk {i}", s) for i, s in enumerate(scores)]
        assert avg_similarity_score(chunks) == pytest.approx(0.8, abs=0.001)

    def test_high_scoring_chunks_above_threshold(self):
        chunks = [_chunk("relevant text", score=0.9)] * 5
        assert avg_similarity_score(chunks) >= 0.7


# ── Integration tests — require indexed knowledge base ────────────────────────

class TestEvaluateQuestion:
    def test_returns_expected_keys(self, require_kb):
        result = evaluate_question("How often should I feed my dog?", ["twice", "morning"])
        assert set(result.keys()) == {
            "question", "chunks_retrieved", "keyword_coverage", "avg_similarity", "sources"
        }

    def test_chunks_retrieved_is_positive(self, require_kb):
        result = evaluate_question("What vaccines does my cat need?", ["vaccine"])
        assert result["chunks_retrieved"] > 0

    def test_coverage_in_valid_range(self, require_kb):
        result = evaluate_question("What fish need in their tank?", ["water", "tank"])
        assert 0.0 <= result["keyword_coverage"] <= 1.0

    def test_similarity_in_valid_range(self, require_kb):
        result = evaluate_question("How do I groom a rabbit?", ["brush", "fur"])
        assert 0.0 <= result["avg_similarity"] <= 1.0

    def test_sources_is_a_list(self, require_kb):
        result = evaluate_question("What should birds eat?", ["seed", "pellet"])
        assert isinstance(result["sources"], list)

    def test_question_preserved_in_result(self, require_kb):
        q = "How much exercise does a dog need daily?"
        result = evaluate_question(q, ["exercise", "walk"])
        assert result["question"] == q


class TestRunEvalSuite:
    def test_returns_expected_keys(self, require_kb):
        result = run_eval_suite()
        assert set(result.keys()) == {
            "questions_evaluated", "avg_keyword_coverage", "avg_similarity_score", "per_question"
        }

    def test_evaluates_all_suite_questions(self, require_kb):
        result = run_eval_suite()
        assert result["questions_evaluated"] == len(EVAL_SUITE)

    def test_per_question_count_matches_suite(self, require_kb):
        result = run_eval_suite()
        assert len(result["per_question"]) == len(EVAL_SUITE)

    def test_avg_coverage_in_valid_range(self, require_kb):
        result = run_eval_suite()
        assert 0.0 <= result["avg_keyword_coverage"] <= 1.0

    def test_avg_similarity_in_valid_range(self, require_kb):
        result = run_eval_suite()
        assert 0.0 <= result["avg_similarity_score"] <= 1.0

    def test_indexed_kb_meets_minimum_coverage(self, require_kb):
        """A well-indexed knowledge base must score at least 50% keyword coverage."""
        result = run_eval_suite()
        assert result["avg_keyword_coverage"] >= 0.5, (
            f"Coverage {result['avg_keyword_coverage']:.0%} is below the 50% floor — "
            "re-index with: python setup_rag.py"
        )
