"""
SAFEGUARD AI - RAG Pipeline
Document ingestion, chunking, embedding, vector storage, and retrieval.
Uses ChromaDB as local vector store.
Supports IBM WatsonX embeddings when configured; falls back to TF-IDF similarity.
"""
import logging
import hashlib
import re
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("ChromaDB not available. RAG will use TF-IDF fallback.")

try:
    from ibm_watsonx_ai.foundation_models import Embeddings
    from ibm_watsonx_ai.metanames import EmbedTextParamsMetaNames as EmbedParams
    WATSONX_AVAILABLE = True
except ImportError:
    WATSONX_AVAILABLE = False

from backend.rag.safety_documents import SAFETY_DOCUMENTS
from backend.config import settings


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector store with its metadata."""
    chunk_id: str
    doc_id: str
    title: str
    source: str
    section: str
    topic: str
    content: str
    relevance_score: float    # 0–1, higher = more relevant
    evidence_type: str = "verified"  # verified, inferred, unknown


class EmbeddingService:
    """
    Generates text embeddings.
    Priority: IBM WatsonX → local sentence-transformers → TF-IDF fallback.
    """

    def __init__(self):
        self._model = None
        self._mode = "tfidf"
        self._model_loaded = False
        # Do NOT load models at import time — defer to first use

    def _ensure_loaded(self):
        """Lazy-load the embedding model on first use."""
        if self._model_loaded:
            return
        self._model_loaded = True
        self._init()

    def _init(self):
        # Try IBM WatsonX embeddings
        if WATSONX_AVAILABLE and settings.ibm_configured:
            try:
                self._model = Embeddings(
                    model_id=settings.IBM_EMBEDDING_MODEL_ID,
                    credentials={
                        "apikey": settings.IBM_WATSONX_API_KEY,
                        "url": settings.IBM_WATSONX_URL,
                    },
                    project_id=settings.IBM_WATSONX_PROJECT_ID,
                )
                self._mode = "watsonx"
                logger.info("Using IBM WatsonX embeddings.")
                return
            except Exception as e:
                logger.warning(f"WatsonX embeddings init failed: {e}")

        # Try local sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._mode = "sentence_transformers"
            logger.info("Using sentence-transformers (all-MiniLM-L6-v2) for embeddings.")
            return
        except ImportError:
            pass

        logger.warning("No embedding model available. Using TF-IDF fallback for RAG retrieval.")
        self._mode = "tfidf"

    def embed(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings for a list of texts. Returns None if not available."""
        self._ensure_loaded()
        if self._mode == "watsonx":
            try:
                result = self._model.embed_documents(texts)
                return result
            except Exception as e:
                logger.error(f"WatsonX embedding error: {e}")
                return None

        if self._mode == "sentence_transformers":
            try:
                vecs = self._model.encode(texts, normalize_embeddings=True)
                return vecs.tolist()
            except Exception as e:
                logger.error(f"Sentence transformer embedding error: {e}")
                return None

        return None

    @property
    def mode(self) -> str:
        return self._mode


class TFIDFRetriever:
    """
    Simple TF-IDF based retrieval as fallback when no embedding model is available.
    """

    def __init__(self, chunks: List[Dict[str, Any]]):
        self._chunks = chunks
        self._vectorizer = None
        self._matrix = None
        self._build_index()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b[a-z]{2,}\b', text.lower())

    def _build_index(self):
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np
            texts = [c["content"] for c in self._chunks]
            self._vectorizer = TfidfVectorizer(
                stop_words="english", ngram_range=(1, 2), max_features=5000
            )
            self._matrix = self._vectorizer.fit_transform(texts)
            logger.info(f"TF-IDF index built with {len(texts)} chunks.")
        except ImportError:
            logger.warning("scikit-learn not available for TF-IDF. Using keyword matching.")

    def retrieve(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        """Returns list of (chunk_index, score) sorted by relevance."""
        if self._vectorizer is not None and self._matrix is not None:
            try:
                import numpy as np
                q_vec = self._vectorizer.transform([query])
                scores = (self._matrix @ q_vec.T).toarray().flatten()
                top_indices = scores.argsort()[::-1][:top_k]
                return [(int(i), float(scores[i])) for i in top_indices if scores[i] > 0]
            except Exception as e:
                logger.warning(f"TF-IDF retrieval error: {e}")

        # Ultimate fallback: keyword matching
        query_words = set(self._tokenize(query))
        results = []
        for i, chunk in enumerate(self._chunks):
            chunk_words = set(self._tokenize(chunk["content"]))
            overlap = len(query_words & chunk_words)
            if overlap > 0:
                results.append((i, overlap / (len(query_words) + 1)))
        return sorted(results, key=lambda x: x[1], reverse=True)[:top_k]


class RAGPipeline:
    """
    Complete RAG pipeline:
    1. Load and chunk safety documents
    2. Generate embeddings
    3. Store in ChromaDB (or use TF-IDF fallback)
    4. Retrieve relevant chunks for a query
    5. Return grounded evidence
    """

    COLLECTION_NAME = "safeguard_safety_docs"

    def __init__(self):
        self._embedding_service = EmbeddingService()
        self._chroma_client = None
        self._collection = None
        self._flat_chunks: List[Dict[str, Any]] = []  # for TF-IDF fallback
        self._tfidf_retriever: Optional[TFIDFRetriever] = None
        self._initialized = False

    def initialize(self):
        """Load documents and build the retrieval index."""
        if self._initialized:
            return

        # Flatten all document chunks
        self._flat_chunks = self._flatten_documents(SAFETY_DOCUMENTS)
        logger.info(f"Loaded {len(self._flat_chunks)} safety document chunks.")

        if CHROMA_AVAILABLE and self._embedding_service.mode != "tfidf":
            self._init_chroma()
        else:
            self._tfidf_retriever = TFIDFRetriever(self._flat_chunks)

        self._initialized = True
        logger.info(f"RAG pipeline initialized (mode: {self._embedding_service.mode}).")

    def _flatten_documents(self, documents: List[Dict]) -> List[Dict[str, Any]]:
        chunks = []
        for doc in documents:
            for i, chunk in enumerate(doc.get("chunks", [])):
                chunk_id = hashlib.md5(
                    f"{doc['doc_id']}_{i}_{chunk['section']}".encode()
                ).hexdigest()[:16]
                chunks.append({
                    "chunk_id": f"{doc['doc_id']}_chunk_{i}",
                    "doc_id": doc["doc_id"],
                    "title": doc["title"],
                    "source": doc["source"],
                    "document_type": doc["document_type"],
                    "machine_categories": doc.get("machine_categories", []),
                    "section": chunk.get("section", ""),
                    "topic": chunk.get("topic", ""),
                    "content": chunk["content"],
                })
        return chunks

    def _init_chroma(self):
        """Initialize ChromaDB and populate with document embeddings."""
        try:
            import os
            persist_dir = settings.CHROMA_PERSIST_DIRECTORY
            os.makedirs(persist_dir, exist_ok=True)

            self._chroma_client = chromadb.PersistentClient(
                path=persist_dir,
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )

            # Check if already populated
            existing_count = self._collection.count()
            if existing_count < len(self._flat_chunks):
                logger.info(f"Indexing {len(self._flat_chunks)} chunks into ChromaDB...")
                self._index_all_chunks()
            else:
                logger.info(f"ChromaDB already has {existing_count} chunks.")

        except Exception as e:
            logger.error(f"ChromaDB init failed: {e}. Falling back to TF-IDF.")
            self._tfidf_retriever = TFIDFRetriever(self._flat_chunks)

    def _index_all_chunks(self):
        """Generate embeddings and store all chunks in ChromaDB."""
        batch_size = 50
        for i in range(0, len(self._flat_chunks), batch_size):
            batch = self._flat_chunks[i:i + batch_size]
            texts = [c["content"] for c in batch]
            embeddings = self._embedding_service.embed(texts)

            ids = [c["chunk_id"] for c in batch]
            metadatas = [
                {
                    "doc_id": c["doc_id"],
                    "title": c["title"],
                    "source": c["source"],
                    "section": c["section"],
                    "topic": c["topic"],
                    "machine_categories": ",".join(c.get("machine_categories", [])),
                }
                for c in batch
            ]

            if embeddings:
                self._collection.upsert(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                )
            else:
                # Fallback: let ChromaDB use its default embedding
                self._collection.upsert(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas,
                )

    def retrieve(
        self,
        query: str,
        machine_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """
        Retrieve the most relevant safety document chunks for a query.
        Returns an empty list with explanation if no relevant evidence found.
        """
        if not self._initialized:
            self.initialize()

        if not query.strip():
            return []

        # ChromaDB retrieval
        if self._collection is not None:
            return self._chroma_retrieve(query, machine_type, top_k)

        # TF-IDF fallback
        if self._tfidf_retriever is not None:
            return self._tfidf_retrieve(query, machine_type, top_k)

        logger.warning("No retrieval mechanism available.")
        return []

    def _chroma_retrieve(
        self, query: str, machine_type: Optional[str], top_k: int
    ) -> List[RetrievedChunk]:
        where = None
        if machine_type:
            where = {"machine_categories": {"$contains": machine_type}}

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(top_k, self._collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"],
            )

            chunks = []
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )):
                # ChromaDB cosine distance: 0=identical, 2=opposite
                relevance = max(0.0, 1.0 - dist / 2.0)
                chunks.append(RetrievedChunk(
                    chunk_id=results["ids"][0][i],
                    doc_id=meta.get("doc_id", ""),
                    title=meta.get("title", ""),
                    source=meta.get("source", ""),
                    section=meta.get("section", ""),
                    topic=meta.get("topic", ""),
                    content=doc,
                    relevance_score=round(relevance, 4),
                    evidence_type="verified",
                ))
            return chunks

        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            return self._tfidf_retrieve(query, machine_type, top_k)

    def _tfidf_retrieve(
        self, query: str, machine_type: Optional[str], top_k: int
    ) -> List[RetrievedChunk]:
        if self._tfidf_retriever is None:
            self._tfidf_retriever = TFIDFRetriever(self._flat_chunks)

        raw = self._tfidf_retriever.retrieve(query, top_k * 2)  # over-retrieve for filtering

        results = []
        for idx, score in raw:
            chunk = self._flat_chunks[idx]
            # Filter by machine type if specified
            if machine_type and machine_type not in chunk.get("machine_categories", []):
                continue
            results.append(RetrievedChunk(
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                title=chunk["title"],
                source=chunk["source"],
                section=chunk["section"],
                topic=chunk["topic"],
                content=chunk["content"],
                relevance_score=round(min(score, 1.0), 4),
                evidence_type="verified",
            ))
            if len(results) >= top_k:
                break

        return results

    def ingest_document(
        self,
        content: str,
        doc_id: str,
        title: str,
        source: str,
        machine_categories: List[str],
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> int:
        """
        Ingest a new document into the RAG pipeline.
        Returns number of chunks created.
        """
        if not self._initialized:
            self.initialize()

        chunks = self._chunk_text(content, chunk_size, chunk_overlap)
        new_flat = []
        for i, chunk_text in enumerate(chunks):
            new_flat.append({
                "chunk_id": f"{doc_id}_chunk_{i}",
                "doc_id": doc_id,
                "title": title,
                "source": source,
                "document_type": "uploaded",
                "machine_categories": machine_categories,
                "section": f"Chunk {i+1}",
                "topic": "general",
                "content": chunk_text,
            })

        self._flat_chunks.extend(new_flat)

        if self._collection is not None:
            texts = [c["content"] for c in new_flat]
            embeddings = self._embedding_service.embed(texts)
            metadatas = [
                {"doc_id": c["doc_id"], "title": c["title"], "source": c["source"],
                 "section": c["section"], "topic": c["topic"],
                 "machine_categories": ",".join(c["machine_categories"])}
                for c in new_flat
            ]
            if embeddings:
                self._collection.upsert(
                    ids=[c["chunk_id"] for c in new_flat],
                    embeddings=embeddings, documents=texts, metadatas=metadatas,
                )
            else:
                self._collection.upsert(
                    ids=[c["chunk_id"] for c in new_flat],
                    documents=texts, metadatas=metadatas,
                )
        else:
            # Rebuild TF-IDF index
            self._tfidf_retriever = TFIDFRetriever(self._flat_chunks)

        return len(new_flat)

    def _rebuild_tfidf_if_needed(self) -> None:
        """Rebuild TF-IDF index when new chunks have been added to _flat_chunks."""
        if self._collection is None and self._flat_chunks:
            self._tfidf_retriever = TFIDFRetriever(self._flat_chunks)

    @staticmethod
    def _chunk_text(text: str, size: int, overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        chunks = []
        current = []
        current_len = 0
        for sent in sentences:
            if current_len + len(sent) > size and current:
                chunks.append(" ".join(current))
                # Keep last few sentences for overlap
                overlap_text = " ".join(current).split()[-overlap // 10:]
                current = overlap_text
                current_len = sum(len(w) for w in current)
            current.append(sent)
            current_len += len(sent)
        if current:
            chunks.append(" ".join(current))
        return chunks if chunks else [text]


# Module-level singleton
rag_pipeline = RAGPipeline()
