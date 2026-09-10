"""
SAFEGUARD AI - Tests for Document Ingestion Pipeline  (Phase 3)

Covers:
  - Text extraction helpers
  - Chunking logic
  - Topic / machine-category auto-tagging
  - build_chunks()
  - DocumentIngestionService.ingest_text()
  - DocumentIngestionService.list_ingested_documents()
  - DocumentIngestionService.delete_document()
  - check_evidence_sufficiency()
  - DB persistence (SafetyDocument + DocumentChunk rows)
  - RAG API endpoints: list, upload/text, get details, delete
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from backend.rag.document_ingestion import (
    chunk_text,
    build_chunks,
    _auto_tag_topics,
    _auto_tag_machines,
    check_evidence_sufficiency,
    DocumentIngestionService,
    INSUFFICIENT_EVIDENCE_RESPONSE,
)
from backend.rag.pipeline import RAGPipeline, RetrievedChunk


# ─────────────────────────────────────────────────────────────────────────────
# Text chunking
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_TEXT = """
Machine guards shall be provided at all points of operation. Guards shall prevent
access to hazardous zones during normal operation.

Temperature monitoring is critical for motor protection. If the motor temperature
exceeds 80 degrees Celsius the system shall generate an alarm and initiate a
controlled shutdown sequence.

Vibration levels shall be monitored continuously. Zone D vibration (above 7.1 mm/s RMS)
is considered severe and requires immediate machine shutdown.

Hydraulic pressure systems shall have pressure relief valves set below the maximum
allowable working pressure. All hydraulic circuits shall be protected.

Emergency stop devices shall be clearly identifiable with red actuator on yellow
background. The emergency stop function shall remain latched until manually reset.
"""


def test_chunk_text_returns_list():
    chunks = chunk_text(SAMPLE_TEXT, chunk_size=300, overlap=50)
    assert isinstance(chunks, list)
    assert len(chunks) >= 1


def test_chunk_text_no_empty_chunks():
    chunks = chunk_text(SAMPLE_TEXT, chunk_size=300)
    for c in chunks:
        assert len(c.strip()) > 0


def test_chunk_text_respects_size():
    """Most chunks should be under chunk_size + reasonable buffer."""
    chunks = chunk_text(SAMPLE_TEXT, chunk_size=200)
    for c in chunks:
        assert len(c) <= 400, f"Chunk is unexpectedly long: {len(c)}"


def test_chunk_text_small_text():
    """Short text should produce exactly one chunk."""
    short = "This is a very short safety note about guards."
    chunks = chunk_text(short, chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0] == short


def test_chunk_text_preserves_content():
    """All key words from source should appear somewhere in the chunks."""
    chunks = chunk_text(SAMPLE_TEXT)
    combined = " ".join(chunks).lower()
    assert "guard" in combined
    assert "temperature" in combined
    assert "vibration" in combined


# ─────────────────────────────────────────────────────────────────────────────
# Auto-tagging
# ─────────────────────────────────────────────────────────────────────────────

def test_auto_tag_topics_guards():
    topics = _auto_tag_topics("Machine guards shall protect operators at all times.")
    assert "guards" in topics


def test_auto_tag_topics_temperature():
    topics = _auto_tag_topics("Motor temperature shall not exceed 80°C.")
    assert "temperature" in topics


def test_auto_tag_topics_emergency_stop():
    topics = _auto_tag_topics("Emergency stop shall be immediately accessible.")
    assert "emergency_stop" in topics


def test_auto_tag_topics_vibration():
    topics = _auto_tag_topics("Vibration above Zone D requires shutdown.")
    assert "vibration" in topics


def test_auto_tag_topics_empty():
    topics = _auto_tag_topics("The quick brown fox jumps over the lazy dog.")
    assert isinstance(topics, list)  # should return empty list, not crash


def test_auto_tag_machines_cnc():
    cats = _auto_tag_machines("CNC machining center spindle speed limits.")
    assert "cnc_machine" in cats


def test_auto_tag_machines_conveyor():
    cats = _auto_tag_machines("Conveyor belt nip point guard requirements.")
    assert "conveyor" in cats


def test_auto_tag_machines_hydraulic():
    cats = _auto_tag_machines("Hydraulic press point of operation guarding.")
    assert "hydraulic_press" in cats


# ─────────────────────────────────────────────────────────────────────────────
# build_chunks()
# ─────────────────────────────────────────────────────────────────────────────

def test_build_chunks_returns_structured_chunks():
    chunks = build_chunks(
        text=SAMPLE_TEXT,
        doc_id="TEST-001",
        title="Test Safety Standard",
        source="TEST",
        document_type="standard",
    )
    assert len(chunks) >= 1
    for c in chunks:
        assert "chunk_id" in c
        assert "doc_id" in c
        assert "content" in c
        assert "section" in c
        assert "topic" in c
        assert "topics" in c
        assert "machine_categories" in c
        assert "char_count" in c


def test_build_chunks_doc_id_populated():
    chunks = build_chunks(
        text="Guards shall be robust. Temperature monitoring is required.",
        doc_id="DOC-XYZ",
        title="Test",
        source="Test",
        document_type="standard",
    )
    for c in chunks:
        assert c["doc_id"] == "DOC-XYZ"
        assert c["title"] == "Test"


def test_build_chunks_auto_detects_categories():
    """Text mentioning conveyor should be tagged with conveyor category."""
    chunks = build_chunks(
        text="Conveyor belt systems require nip point guarding at all pulleys.",
        doc_id="CONV-001",
        title="Conveyor Safety",
        source="CEMA",
        document_type="guideline",
        machine_categories=None,  # let auto-detection run
    )
    all_cats = set(cat for c in chunks for cat in c["machine_categories"])
    assert "conveyor" in all_cats


def test_build_chunks_explicit_categories():
    """Explicit categories should override auto-detection."""
    chunks = build_chunks(
        text="General safety requirements for all machinery.",
        doc_id="GEN-001",
        title="General Safety",
        source="OSHA",
        document_type="regulation",
        machine_categories=["cnc_machine", "hydraulic_press"],
    )
    for c in chunks:
        assert c["machine_categories"] == ["cnc_machine", "hydraulic_press"]


def test_build_chunks_char_count_accurate():
    chunks = build_chunks(
        text=SAMPLE_TEXT,
        doc_id="CC-001",
        title="Test",
        source="Test",
        document_type="standard",
    )
    for c in chunks:
        assert c["char_count"] == len(c["content"])


# ─────────────────────────────────────────────────────────────────────────────
# DocumentIngestionService — in-memory (no DB)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def fresh_rag():
    """Fresh RAG pipeline (not the module-level singleton)."""
    pipeline = RAGPipeline()
    pipeline.initialize()
    return pipeline


def test_ingest_text_returns_summary(fresh_rag):
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    result = svc.ingest_text(
        text=SAMPLE_TEXT,
        title="Test Safety Guideline",
        source="Test Standard 1.0",
        document_type="guideline",
        doc_id="INGEST-TEST-001",
    )
    assert result["status"] == "ingested"
    assert result["chunk_count"] >= 1
    assert result["doc_id"] == "INGEST-TEST-001"
    assert isinstance(result["machine_categories"], list)
    assert isinstance(result["topics"], list)


def test_ingest_text_chunks_searchable(fresh_rag):
    """After ingestion, the document should be retrievable via RAG query."""
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    svc.ingest_text(
        text="Laser safety interlocks shall prevent emission when enclosure is open.",
        title="Laser Safety Standard",
        source="IEC 60825",
        document_type="standard",
        doc_id="LASER-INGEST-001",
    )
    results = fresh_rag.retrieve("laser interlock enclosure", top_k=5)
    doc_ids = [r.doc_id for r in results]
    assert "LASER-INGEST-001" in doc_ids, "Ingested document should be retrievable"


def test_ingest_text_appears_in_list(fresh_rag):
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    svc.ingest_text(
        text="Electrical safety requirements for motor drives.",
        title="Motor Drive Safety",
        source="IEC 61800",
        document_type="standard",
        doc_id="MOTOR-LIST-001",
    )
    docs = svc.list_ingested_documents()
    doc_ids = [d["doc_id"] for d in docs]
    assert "MOTOR-LIST-001" in doc_ids


def test_ingest_empty_text_raises(fresh_rag):
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    with pytest.raises(ValueError):
        svc.ingest_text(
            text="   ",
            title="Empty Doc",
            source="Test",
            document_type="standard",
        )


def test_ingest_text_without_doc_id_generates_one(fresh_rag):
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    result = svc.ingest_text(
        text="Pressure relief valve requirements for all hydraulic circuits.",
        title="Hydraulic Safety",
        source="ISO 4413",
        document_type="standard",
        doc_id=None,  # should auto-generate
    )
    assert result["doc_id"]
    assert len(result["doc_id"]) > 5


def test_delete_document(fresh_rag):
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    svc.ingest_text(
        text="Temporary document for deletion test.",
        title="Delete Test",
        source="Test",
        document_type="standard",
        doc_id="DELETE-ME-001",
    )
    # Verify it was added
    assert any(c["doc_id"] == "DELETE-ME-001" for c in fresh_rag._flat_chunks)

    # Delete it
    removed = svc.delete_document("DELETE-ME-001")
    assert removed is True

    # Verify it's gone from flat chunks
    assert not any(c["doc_id"] == "DELETE-ME-001" for c in fresh_rag._flat_chunks)


def test_delete_nonexistent_document(fresh_rag):
    svc = DocumentIngestionService(fresh_rag, db_session_factory=None)
    removed = svc.delete_document("DOES-NOT-EXIST-XYZ")
    assert removed is False


# ─────────────────────────────────────────────────────────────────────────────
# DocumentIngestionService — with SQL DB
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def in_memory_db_for_rag():
    """In-memory SQLite DB with all tables created."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.database.models import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    class _Factory:
        def __call__(self):
            return factory()
        def __enter__(self):
            self._s = factory()
            return self._s
        def __exit__(self, *a):
            self._s.close()

    return _Factory()


@pytest.fixture(scope="module")
def db_rag_pipeline():
    pipeline = RAGPipeline()
    pipeline.initialize()
    return pipeline


def test_ingest_persists_to_db(db_rag_pipeline, in_memory_db_for_rag):
    from backend.database.models import SafetyDocument, DocumentChunk

    svc = DocumentIngestionService(db_rag_pipeline, in_memory_db_for_rag)
    svc.ingest_text(
        text=SAMPLE_TEXT,
        title="DB Persistence Test",
        source="DB Test Standard",
        document_type="standard",
        doc_id="DB-PERSIST-001",
    )

    with in_memory_db_for_rag() as db:
        doc_row = db.query(SafetyDocument).filter(
            SafetyDocument.doc_id == "DB-PERSIST-001"
        ).first()
        assert doc_row is not None, "SafetyDocument row should be created"
        assert doc_row.title == "DB Persistence Test"
        assert doc_row.chunk_count >= 1

        chunk_rows = db.query(DocumentChunk).filter(
            DocumentChunk.doc_id == "DB-PERSIST-001"
        ).all()
        assert len(chunk_rows) >= 1, "DocumentChunk rows should be created"


def test_ingest_db_chunk_fields(db_rag_pipeline, in_memory_db_for_rag):
    """DocumentChunk rows should have content and topic fields populated."""
    from backend.database.models import DocumentChunk

    with in_memory_db_for_rag() as db:
        rows = db.query(DocumentChunk).filter(
            DocumentChunk.doc_id == "DB-PERSIST-001"
        ).all()
    for row in rows:
        assert row.content and len(row.content) > 10
        assert row.char_count and row.char_count > 0
        assert row.section


def test_list_from_db(db_rag_pipeline, in_memory_db_for_rag):
    svc = DocumentIngestionService(db_rag_pipeline, in_memory_db_for_rag)
    docs = svc.list_ingested_documents()
    doc_ids = [d["doc_id"] for d in docs]
    assert "DB-PERSIST-001" in doc_ids


def test_ingest_twice_is_idempotent(db_rag_pipeline, in_memory_db_for_rag):
    """Re-ingesting the same doc_id should update, not duplicate."""
    from backend.database.models import SafetyDocument

    svc = DocumentIngestionService(db_rag_pipeline, in_memory_db_for_rag)
    svc.ingest_text(
        text="Updated content for idempotency test.",
        title="Idempotency Test Updated",
        source="Test",
        document_type="standard",
        doc_id="IDEMPOTENT-001",
    )
    svc.ingest_text(
        text="Updated content for idempotency test.",
        title="Idempotency Test Updated",
        source="Test",
        document_type="standard",
        doc_id="IDEMPOTENT-001",
    )
    with in_memory_db_for_rag() as db:
        count = db.query(SafetyDocument).filter(
            SafetyDocument.doc_id == "IDEMPOTENT-001"
        ).count()
    assert count == 1, "Should not duplicate SafetyDocument rows"


# ─────────────────────────────────────────────────────────────────────────────
# Evidence sufficiency check
# ─────────────────────────────────────────────────────────────────────────────

def _make_chunk(relevance: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id="c1", doc_id="D1", title="T", source="S",
        section="1", topic="guards", content="Guard text.",
        relevance_score=relevance, evidence_type="verified",
    )


def test_evidence_sufficient():
    chunks = [_make_chunk(0.7), _make_chunk(0.5)]
    sufficient, resp = check_evidence_sufficiency(chunks, min_relevance=0.1)
    assert sufficient is True
    assert resp["evidence_status"] == "verified"


def test_evidence_insufficient_low_relevance():
    chunks = [_make_chunk(0.02), _make_chunk(0.01)]
    sufficient, resp = check_evidence_sufficiency(chunks, min_relevance=0.1)
    assert sufficient is False
    assert resp["evidence_status"] == "insufficient"
    assert "Insufficient evidence" in resp["message"]


def test_evidence_insufficient_empty():
    sufficient, resp = check_evidence_sufficiency([], min_relevance=0.1)
    assert sufficient is False
    assert resp["evidence_status"] == "insufficient"


def test_insufficient_evidence_response_has_recommendation():
    assert "recommendation" in INSUFFICIENT_EVIDENCE_RESPONSE


# ─────────────────────────────────────────────────────────────────────────────
# RAG API endpoints (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client_rag():
    from unittest.mock import patch
    with patch('backend.rag.pipeline.rag_pipeline') as mock_rag:
        mock_rag._initialized = True
        mock_rag._embedding_service = type("ES", (), {"mode": "tfidf"})()
        mock_rag._flat_chunks = [
            {
                "chunk_id": "builtin_c0",
                "doc_id": "ISO-13849-1",
                "title": "ISO 13849-1",
                "source": "ISO 13849-1:2015",
                "document_type": "standard",
                "machine_categories": ["cnc_machine"],
                "section": "4.1",
                "topic": "safety_controls",
                "topics": ["safety_controls"],
                "content": "Guards shall protect operators from all hazardous zones.",
                "char_count": 55,
            }
        ]
        mock_rag._collection = None
        mock_rag._tfidf_retriever = None
        mock_rag._rebuild_tfidf_if_needed = lambda: None

        from backend.api.main import app
        app.router.lifespan_handler = None
        from fastapi.testclient import TestClient
        yield TestClient(app)


def test_api_rag_list_documents(api_client_rag):
    r = api_client_rag.get("/api/v1/rag/documents")
    assert r.status_code == 200
    data = r.json()
    assert "built_in" in data
    assert "uploaded" in data
    assert "total" in data
    assert isinstance(data["built_in"], list)
    assert len(data["built_in"]) >= 1


def test_api_rag_query(api_client_rag):
    r = api_client_rag.post("/api/v1/rag/query", json={
        "query": "machine guard requirements",
        "top_k": 5,
    })
    assert r.status_code == 200
    data = r.json()
    assert "query" in data
    assert "results" in data


def test_api_rag_upload_text(api_client_rag):
    r = api_client_rag.post("/api/v1/rag/documents/upload/text", json={
        "title": "Test Safety Note",
        "source": "Test Standard 2.0",
        "content": "All CNC machine guards shall be interlocked to prevent spindle access during operation.",
        "document_type": "guideline",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ingested"
    assert data["chunk_count"] >= 1
    assert "doc_id" in data


def test_api_rag_upload_text_empty_content(api_client_rag):
    r = api_client_rag.post("/api/v1/rag/documents/upload/text", json={
        "title": "Empty Doc",
        "source": "Test",
        "content": "   ",
    })
    assert r.status_code == 400


def test_api_rag_upload_text_no_title(api_client_rag):
    r = api_client_rag.post("/api/v1/rag/documents/upload/text", json={
        "title": "",
        "source": "Test",
        "content": "Some valid content about guards.",
    })
    assert r.status_code == 400


def test_api_rag_get_builtin_document(api_client_rag):
    r = api_client_rag.get("/api/v1/rag/documents/ISO-13849-1")
    assert r.status_code == 200
    data = r.json()
    assert data["doc_id"] == "ISO-13849-1"
    assert data["storage"] == "built-in"
    assert "chunks" in data


def test_api_rag_get_unknown_document(api_client_rag):
    r = api_client_rag.get("/api/v1/rag/documents/UNKNOWN-DOC-XYZ")
    assert r.status_code == 404


def test_api_rag_delete_builtin_forbidden(api_client_rag):
    r = api_client_rag.delete("/api/v1/rag/documents/ISO-13849-1")
    assert r.status_code == 403


def test_api_rag_delete_nonexistent(api_client_rag):
    r = api_client_rag.delete("/api/v1/rag/documents/NONEXISTENT-999")
    assert r.status_code == 404
