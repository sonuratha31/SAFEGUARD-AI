"""
SAFEGUARD AI - Document Ingestion Pipeline  (Phase 3)

Supports PDF, TXT, and DOCX document parsing, chunking, metadata extraction,
embedding generation, and storage in:
  - ChromaDB (vector store for RAG retrieval)
  - SQLite (SafetyDocument + DocumentChunk tables for audit trail)

Document → extraction → chunking → metadata tagging → embeddings
→ vector database → SQL metadata store → retrieval-ready.

Never fabricates safety regulations.
If evidence cannot be found, returns INSUFFICIENT_EVIDENCE signal.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Optional parser libraries (graceful degradation if not installed)
# ─────────────────────────────────────────────────────────────────────────────

def _try_import_pdf():
    try:
        import pdfplumber
        return pdfplumber
    except ImportError:
        pass
    try:
        import pypdf
        return pypdf
    except ImportError:
        pass
    try:
        import PyPDF2
        return PyPDF2
    except ImportError:
        return None

def _try_import_docx():
    try:
        import docx
        return docx
    except ImportError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Topic / machine-category auto-tagging
# ─────────────────────────────────────────────────────────────────────────────

TOPIC_KEYWORDS: Dict[str, List[str]] = {
    "guards":            ["guard", "guarding", "barrier", "enclosure", "shield"],
    "interlocks":        ["interlock", "interlocking", "lockout", "tagout", "loto"],
    "emergency_stop":    ["emergency stop", "estop", "e-stop", "mushroom", "category 0"],
    "temperature":       ["temperature", "thermal", "overheat", "cooling", "heat"],
    "vibration":         ["vibration", "vibrate", "oscillat", "resonan", "bearing"],
    "pressure":          ["pressure", "hydraulic", "pneumatic", "psi", "bar", "relief valve"],
    "load":              ["load", "overload", "capacity", "torque", "current"],
    "maintenance":       ["maintenance", "inspect", "service", "lubrication", "wear", "schedule"],
    "electrical_safety": ["electrical", "voltage", "current", "overcurrent", "ground fault", "arc"],
    "safety_controls":   ["safety function", "plc", "control system", "safety-rated", "sis"],
    "safety_distances":  ["safety distance", "reach distance", "clearance"],
}

MACHINE_KEYWORDS: Dict[str, List[str]] = {
    "cnc_machine":      ["cnc", "machining center", "milling", "lathe", "spindle", "toolpath"],
    "hydraulic_press":  ["hydraulic press", "press", "punch", "die", "forging", "stamping"],
    "industrial_motor": ["motor", "drive", "vfd", "inverter", "shaft", "rpm", "induction"],
    "compressor":       ["compressor", "compressed air", "air pressure", "piston pump"],
    "conveyor":         ["conveyor", "belt", "nip point", "pulley", "chain drive", "roller"],
}


def _auto_tag_topics(text: str) -> List[str]:
    """Identify relevant safety topics from text content."""
    lower = text.lower()
    return [topic for topic, kws in TOPIC_KEYWORDS.items() if any(kw in lower for kw in kws)]


def _auto_tag_machines(text: str) -> List[str]:
    """Identify relevant machine categories from text content."""
    lower = text.lower()
    return [cat for cat, kws in MACHINE_KEYWORDS.items() if any(kw in lower for kw in kws)]


# ─────────────────────────────────────────────────────────────────────────────
# Text extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_file(file_path: str, file_type: Optional[str] = None) -> str:
    """
    Extract plain text from a document file.

    Supports: .txt, .pdf (via pdfplumber/pypdf/PyPDF2), .docx (via python-docx)

    Returns the extracted text, or raises ValueError if the format is unsupported
    or a required library is not available.
    """
    path = Path(file_path)
    ext = (file_type or path.suffix).lower().lstrip(".")

    if ext == "txt":
        return _extract_txt(path)
    elif ext == "pdf":
        return _extract_pdf(path)
    elif ext in ("docx", "doc"):
        return _extract_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Supported: txt, pdf, docx")


def _extract_txt(path: Path) -> str:
    """Read a plain-text file."""
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Could not decode {path} with any known encoding")


def _extract_pdf(path: Path) -> str:
    """Extract text from a PDF using best available library."""
    pdf_lib = _try_import_pdf()
    if pdf_lib is None:
        raise ValueError(
            "PDF extraction requires pdfplumber or pypdf. "
            "Install with: pip install pdfplumber"
        )

    mod_name = pdf_lib.__name__

    if mod_name == "pdfplumber":
        pages = []
        with pdf_lib.open(str(path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)

    elif mod_name == "pypdf":
        import pypdf as pypdf_mod
        pages = []
        with pypdf_mod.PdfReader(str(path)) as reader:
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)

    elif mod_name == "PyPDF2":
        import PyPDF2
        pages = []
        with open(str(path), "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        return "\n\n".join(pages)

    raise ValueError("PDF library detected but not recognized")


def _extract_docx(path: Path) -> str:
    """Extract text from a DOCX file using python-docx."""
    docx_lib = _try_import_docx()
    if docx_lib is None:
        raise ValueError(
            "DOCX extraction requires python-docx. "
            "Install with: pip install python-docx"
        )
    doc = docx_lib.Document(str(path))
    paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    # Also extract tables
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)
    return "\n\n".join(paragraphs)


# ─────────────────────────────────────────────────────────────────────────────
# Chunking
# ─────────────────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 600,
    overlap: int = 80,
    min_chunk_len: int = 50,
) -> List[str]:
    """
    Split text into overlapping chunks suitable for embedding.

    Strategy:
    1. Split on double newlines (paragraphs/sections) first.
    2. If a paragraph is > chunk_size, split it on sentences.
    3. Accumulate chunks with overlap.
    """
    # Normalize whitespace
    text = re.sub(r'\n{3,}', '\n\n', text.strip())
    paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]

    sentences: List[str] = []
    for para in paragraphs:
        # Split long paragraphs into sentences
        if len(para) > chunk_size:
            sents = re.split(r'(?<=[.!?;])\s+', para)
            sentences.extend([s.strip() for s in sents if s.strip()])
        else:
            sentences.append(para)

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent)
        if current_len + sent_len > chunk_size and current:
            chunk_text_str = " ".join(current)
            if len(chunk_text_str) >= min_chunk_len:
                chunks.append(chunk_text_str)
            # Overlap: keep last ~(overlap/chunk_size) fraction of sentences
            keep = max(1, len(current) // 4)
            current = current[-keep:]
            current_len = sum(len(s) for s in current)
        current.append(sent)
        current_len += sent_len

    if current:
        chunk_text_str = " ".join(current)
        if len(chunk_text_str) >= min_chunk_len:
            chunks.append(chunk_text_str)

    return chunks if chunks else [text[:chunk_size]]


# ─────────────────────────────────────────────────────────────────────────────
# Structured chunk builder
# ─────────────────────────────────────────────────────────────────────────────

def build_chunks(
    text: str,
    doc_id: str,
    title: str,
    source: str,
    document_type: str,
    machine_categories: Optional[List[str]] = None,
    topics: Optional[List[str]] = None,
    chunk_size: int = 600,
    overlap: int = 80,
) -> List[Dict[str, Any]]:
    """
    Given extracted text, produce a list of structured chunk dicts ready for
    embedding and storage.

    Each chunk dict matches the schema expected by RAGPipeline._flat_chunks.
    """
    raw_chunks = chunk_text(text, chunk_size, overlap)

    if machine_categories is None:
        machine_categories = _auto_tag_machines(text)
    if not machine_categories:
        # Default to all machine types if no specific ones detected
        machine_categories = [
            "cnc_machine", "hydraulic_press", "industrial_motor",
            "compressor", "conveyor",
        ]

    if topics is None:
        topics = _auto_tag_topics(text)

    result: List[Dict[str, Any]] = []
    for i, chunk_content in enumerate(raw_chunks):
        chunk_topics = _auto_tag_topics(chunk_content) or topics or ["general"]
        chunk_id = _make_chunk_id(doc_id, i, chunk_content)
        result.append({
            "chunk_id":          chunk_id,
            "doc_id":            doc_id,
            "title":             title,
            "source":            source,
            "document_type":     document_type,
            "machine_categories": machine_categories,
            "section":           f"Chunk {i + 1} of {len(raw_chunks)}",
            "topic":             chunk_topics[0] if chunk_topics else "general",
            "topics":            chunk_topics,
            "content":           chunk_content,
            "char_count":        len(chunk_content),
        })

    return result


def _make_chunk_id(doc_id: str, index: int, content: str) -> str:
    h = hashlib.md5(f"{doc_id}_{index}_{content[:40]}".encode()).hexdigest()[:12]
    return f"{doc_id}_c{index:04d}_{h}"


# ─────────────────────────────────────────────────────────────────────────────
# Document ingestion service
# ─────────────────────────────────────────────────────────────────────────────

class DocumentIngestionService:
    """
    Orchestrates the full document ingestion pipeline:
      file → extract text → chunk → tag → embed → ChromaDB + SQL DB

    Usage::
        service = DocumentIngestionService(rag_pipeline, session_factory)
        result  = service.ingest_file("path/to/doc.pdf", title="My Doc", ...)
    """

    def __init__(self, rag_pipeline, db_session_factory=None):
        """
        Parameters
        ----------
        rag_pipeline        : RAGPipeline singleton
        db_session_factory  : callable returning a SQLAlchemy Session (optional)
        """
        self._rag = rag_pipeline
        self._db = db_session_factory

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def ingest_file(
        self,
        file_path: str,
        title: str,
        source: str,
        document_type: str = "standard",
        machine_categories: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        doc_id: Optional[str] = None,
        chunk_size: int = 600,
        overlap: int = 80,
    ) -> Dict[str, Any]:
        """
        Full pipeline: read file → extract → chunk → embed → store.

        Returns a summary dict with doc_id, chunk_count, topics, categories.
        Raises ValueError for unsupported file types or extraction errors.
        """
        path = Path(file_path)
        ext = path.suffix.lower().lstrip(".")

        # Extract text
        raw_text = extract_text_from_file(file_path)
        if not raw_text.strip():
            raise ValueError("Document appears to be empty or unreadable.")

        return self.ingest_text(
            text              = raw_text,
            title             = title,
            source            = source,
            document_type     = document_type,
            machine_categories= machine_categories,
            topics            = topics,
            doc_id            = doc_id or _generate_doc_id(title, source),
            file_path         = file_path,
            file_type         = ext,
            chunk_size        = chunk_size,
            overlap           = overlap,
        )

    def ingest_text(
        self,
        text: str,
        title: str,
        source: str,
        document_type: str = "standard",
        machine_categories: Optional[List[str]] = None,
        topics: Optional[List[str]] = None,
        doc_id: Optional[str] = None,
        file_path: Optional[str] = None,
        file_type: Optional[str] = None,
        chunk_size: int = 600,
        overlap: int = 80,
    ) -> Dict[str, Any]:
        """
        Ingest raw text (used when content is already extracted or comes from API).
        """
        if text is None or not str(text).strip():
            raise ValueError("Document content is empty")

        if not self._rag._initialized:
            self._rag.initialize()

        effective_doc_id = doc_id or _generate_doc_id(title, source)

        chunks = build_chunks(
            text               = text,
            doc_id             = effective_doc_id,
            title              = title,
            source             = source,
            document_type      = document_type,
            machine_categories = machine_categories,
            topics             = topics,
            chunk_size         = chunk_size,
            overlap            = overlap,
        )

        if not chunks:
            raise ValueError("No usable chunks could be extracted from the document.")

        detected_categories = chunks[0]["machine_categories"]
        detected_topics = list({t for c in chunks for t in c["topics"]})

        # Add chunks to the RAG pipeline's in-memory store and vector DB
        self._rag._flat_chunks.extend(chunks)
        self._rag._rebuild_tfidf_if_needed()

        if self._rag._collection is not None:
            self._index_to_chroma(chunks)

        # Persist metadata to SQL database
        if self._db is not None:
            self._persist_to_db(
                doc_id            = effective_doc_id,
                title             = title,
                source            = source,
                document_type     = document_type,
                file_path         = file_path,
                file_type         = file_type,
                machine_categories= detected_categories,
                topics            = detected_topics,
                chunks            = chunks,
            )

        logger.info(
            "Ingested document '%s' (%s): %d chunks, categories=%s",
            title, effective_doc_id, len(chunks), detected_categories,
        )

        return {
            "doc_id":            effective_doc_id,
            "title":             title,
            "source":            source,
            "document_type":     document_type,
            "chunk_count":       len(chunks),
            "machine_categories": detected_categories,
            "topics":            detected_topics,
            "status":            "ingested",
        }

    def list_ingested_documents(self) -> List[Dict[str, Any]]:
        """
        Return metadata for all documents stored in the SQL database.
        Falls back to in-memory chunk list if DB is unavailable.
        """
        if self._db is not None:
            try:
                return self._list_from_db()
            except Exception as e:
                logger.warning("DB list failed (%s); falling back to memory", e)

        return self._list_from_memory()

    def delete_document(self, doc_id: str) -> bool:
        """
        Remove a document from ChromaDB, in-memory chunks, and the SQL database.
        Returns True only when the requested document actually existed and was removed.
        """
        existed = False

        # Remove from in-memory flat chunks
        before = len(self._rag._flat_chunks)
        filtered_chunks = [
            c for c in self._rag._flat_chunks if c["doc_id"] != doc_id
        ]
        if len(filtered_chunks) < before:
            existed = True
            self._rag._flat_chunks = filtered_chunks
            self._rag._rebuild_tfidf_if_needed()
        else:
            self._rag._flat_chunks = filtered_chunks

        # Remove from ChromaDB
        if self._rag._collection is not None:
            try:
                ids = self._rag._collection.get(where={"doc_id": doc_id})["ids"]
                if ids:
                    self._rag._collection.delete(ids=ids)
                    existed = True
            except Exception as e:
                logger.warning("ChromaDB delete failed for %s: %s", doc_id, e)

        # Remove from SQL DB
        if self._db is not None:
            try:
                from backend.database.models import SafetyDocument, DocumentChunk
                with self._db() as db:
                    deleted_chunks = db.query(DocumentChunk).filter(
                        DocumentChunk.doc_id == doc_id
                    ).delete()
                    deleted_doc = db.query(SafetyDocument).filter(
                        SafetyDocument.doc_id == doc_id
                    ).delete()
                    db.commit()
                    if deleted_chunks or deleted_doc:
                        existed = True
            except Exception as e:
                logger.warning("DB delete failed for %s: %s", doc_id, e)

        return existed

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _index_to_chroma(self, chunks: List[Dict[str, Any]]) -> None:
        """Write chunks to ChromaDB (with embeddings when available)."""
        texts     = [c["content"] for c in chunks]
        ids       = [c["chunk_id"] for c in chunks]
        metadatas = [
            {
                "doc_id":            c["doc_id"],
                "title":             c["title"],
                "source":            c["source"],
                "section":          c["section"],
                "topic":             c["topic"],
                "machine_categories": ",".join(c["machine_categories"]),
            }
            for c in chunks
        ]

        try:
            embeddings = self._rag._embedding_service.embed(texts)
            if embeddings:
                self._rag._collection.upsert(
                    ids=ids, embeddings=embeddings,
                    documents=texts, metadatas=metadatas,
                )
            else:
                self._rag._collection.upsert(
                    ids=ids, documents=texts, metadatas=metadatas,
                )
        except Exception as e:
            logger.error("ChromaDB upsert error: %s", e)

    def _persist_to_db(
        self,
        doc_id: str,
        title: str,
        source: str,
        document_type: str,
        file_path: Optional[str],
        file_type: Optional[str],
        machine_categories: List[str],
        topics: List[str],
        chunks: List[Dict[str, Any]],
    ) -> None:
        """Write SafetyDocument + DocumentChunk rows to the SQL database."""
        try:
            from backend.database.models import SafetyDocument, DocumentChunk
            with self._db() as db:
                # Upsert SafetyDocument
                existing = db.query(SafetyDocument).filter(
                    SafetyDocument.doc_id == doc_id
                ).first()
                now = datetime.now(timezone.utc)

                if existing:
                    existing.title              = title
                    existing.source             = source
                    existing.document_type      = document_type
                    existing.file_path          = file_path
                    existing.file_type          = file_type
                    existing.machine_categories = machine_categories
                    existing.topics             = topics
                    existing.chunk_count        = len(chunks)
                    existing.indexed_at         = now
                else:
                    doc_row = SafetyDocument(
                        doc_id             = doc_id,
                        title              = title,
                        source             = source,
                        document_type      = document_type,
                        file_path          = file_path,
                        file_type          = file_type,
                        machine_categories = machine_categories,
                        topics             = topics,
                        chunk_count        = len(chunks),
                        is_active          = True,
                        indexed_at         = now,
                        created_at         = now,
                    )
                    db.add(doc_row)

                # Delete old chunks for this doc
                db.query(DocumentChunk).filter(
                    DocumentChunk.doc_id == doc_id
                ).delete()

                # Insert new chunks
                for c in chunks:
                    db.add(DocumentChunk(
                        chunk_id           = c["chunk_id"],
                        doc_id             = doc_id,
                        section            = c["section"],
                        topic              = c["topic"],
                        content            = c["content"],
                        char_count         = c["char_count"],
                        machine_categories = c["machine_categories"],
                        topics             = c["topics"],
                        created_at         = now,
                    ))

                db.commit()
        except Exception as e:
            logger.warning("DB persist failed for doc %s: %s", doc_id, e)

    def _list_from_db(self) -> List[Dict[str, Any]]:
        from backend.database.models import SafetyDocument
        with self._db() as db:
            rows = db.query(SafetyDocument).filter(
                SafetyDocument.is_active == True
            ).order_by(SafetyDocument.created_at.desc()).all()
        return [
            {
                "doc_id":            r.doc_id,
                "title":             r.title,
                "source":            r.source,
                "document_type":     r.document_type,
                "machine_categories": r.machine_categories or [],
                "topics":            r.topics or [],
                "chunk_count":       r.chunk_count,
                "file_type":         r.file_type,
                "indexed_at":        r.indexed_at.isoformat() if r.indexed_at else None,
                "storage":           "database",
            }
            for r in rows
        ]

    def _list_from_memory(self) -> List[Dict[str, Any]]:
        """Summarize documents from in-memory flat chunks."""
        seen: Dict[str, Dict[str, Any]] = {}
        for c in self._rag._flat_chunks:
            did = c["doc_id"]
            if did not in seen:
                seen[did] = {
                    "doc_id":            did,
                    "title":             c["title"],
                    "source":            c["source"],
                    "document_type":     c.get("document_type", "standard"),
                    "machine_categories": c.get("machine_categories", []),
                    "topics":            [],
                    "chunk_count":       0,
                    "storage":           "memory",
                }
            seen[did]["chunk_count"] += 1
            for t in c.get("topics", [c.get("topic", "general")]):
                if t not in seen[did]["topics"]:
                    seen[did]["topics"].append(t)
        return list(seen.values())


# ─────────────────────────────────────────────────────────────────────────────
# Insufficient Evidence sentinel
# ─────────────────────────────────────────────────────────────────────────────

INSUFFICIENT_EVIDENCE_RESPONSE = {
    "evidence_status": "insufficient",
    "message": "Insufficient evidence to verify this requirement.",
    "chunks": [],
    "recommendation": (
        "Upload relevant safety standards or operating manuals to enable "
        "evidence-based compliance verification."
    ),
}


def check_evidence_sufficiency(
    chunks: list,
    min_relevance: float = 0.10,
    min_chunks: int = 1,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Determine whether retrieved chunks constitute sufficient evidence.

    Returns (sufficient: bool, response_dict)
    """
    relevant = [c for c in chunks if getattr(c, "relevance_score", 0) >= min_relevance]
    if len(relevant) >= min_chunks:
        return True, {"evidence_status": "verified", "chunks": relevant}
    return False, INSUFFICIENT_EVIDENCE_RESPONSE.copy()


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _generate_doc_id(title: str, source: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", f"{source}-{title}")[:40].strip("-").upper()
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"{slug}-{short_uuid}"
