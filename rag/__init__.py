from .pipeline import ask, retrieve, is_index_populated
from .ingest import ingest_file, ingest_bytes, ingest_text, remove_source
from .evaluator import run_eval_suite, evaluate_question
from .vector_store import list_sources, count_by_category

__all__ = [
    # Core pipeline
    "ask",
    "retrieve",
    "is_index_populated",
    # Ingestion
    "ingest_file",
    "ingest_bytes",
    "ingest_text",
    "remove_source",
    # Evaluation
    "run_eval_suite",
    "evaluate_question",
    # Vector store inspection
    "list_sources",
    "count_by_category",
]
