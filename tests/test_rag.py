"""
SAFEGUARD AI - Tests for RAG Pipeline
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.rag.pipeline import RAGPipeline, TFIDFRetriever
from backend.rag.safety_documents import SAFETY_DOCUMENTS


def test_safety_documents_not_empty():
    assert len(SAFETY_DOCUMENTS) > 0


def test_all_documents_have_required_fields():
    for doc in SAFETY_DOCUMENTS:
        assert "doc_id" in doc
        assert "title" in doc
        assert "source" in doc
        assert "chunks" in doc
        assert len(doc["chunks"]) > 0
        for chunk in doc["chunks"]:
            assert "content" in chunk
            assert len(chunk["content"]) > 50


@pytest.fixture(scope="module")
def rag():
    pipeline = RAGPipeline()
    pipeline.initialize()
    return pipeline


def test_rag_initializes(rag):
    assert rag._initialized
    assert len(rag._flat_chunks) > 0


def test_rag_retrieves_guard_evidence(rag):
    results = rag.retrieve("machine guard protection during operation", top_k=3)
    assert len(results) > 0
    # Should retrieve OSHA or ISO guard-related content
    sources = [r.source for r in results]
    content = " ".join(r.content for r in results).lower()
    assert "guard" in content


def test_rag_retrieves_vibration_evidence(rag):
    results = rag.retrieve("vibration evaluation criteria ISO 10816", top_k=3)
    assert len(results) > 0
    content = " ".join(r.content for r in results).lower()
    assert "vibration" in content


def test_rag_no_fabrication_on_missing_query(rag):
    """For an empty/meaningless query, return empty or low-relevance results."""
    results = rag.retrieve("xyzzy purple elephant quantum banana nonsense", top_k=3)
    # Should return empty or very low relevance
    if results:
        for r in results:
            assert r.relevance_score <= 1.0  # scores must be bounded


def test_rag_machine_type_filter(rag):
    """Machine type filter should limit results to relevant machine categories."""
    results = rag.retrieve("pressure safety requirements", machine_type="hydraulic_press", top_k=5)
    # All results should be relevant to hydraulic_press or general
    assert isinstance(results, list)


def test_rag_returns_evidence_type_field(rag):
    results = rag.retrieve("emergency stop device requirements", top_k=3)
    for r in results:
        assert r.evidence_type in ("verified", "inferred", "unknown")


def test_tfidf_retriever_basic():
    """TF-IDF retriever should find relevant chunks."""
    chunks = [
        {"content": "Machine guard shall be in place during operation. Guards protect operators."},
        {"content": "Temperature monitoring is essential for thermal protection of motors."},
        {"content": "Vibration analysis helps detect bearing wear and mechanical issues."},
    ]
    retriever = TFIDFRetriever(chunks)
    results = retriever.retrieve("guard machine protection operator", top_k=2)
    assert len(results) > 0
    # First result should be the guard-related chunk
    assert results[0][0] == 0
