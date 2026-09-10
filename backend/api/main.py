"""
SAFEGUARD AI - FastAPI Application  (Phase 2 complete)
Main backend entry point with all API routes.
"""
from __future__ import annotations

import logging
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend.config import settings
from backend.telemetry.service import telemetry_service
from backend.agents.orchestrator import safety_orchestrator
from backend.rag import pipeline as rag_pipeline_module
from backend.simulation.simulator import MACHINE_CONFIGS, INJECTABLE_SCENARIOS, SCENARIO_LABELS


def get_rag_pipeline():
    """Return the current module-level RAG singleton, avoiding stale import aliases."""
    return rag_pipeline_module.rag_pipeline

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Background simulation task
_sim_task: Optional[asyncio.Task] = None
_sim_running = False


async def _simulation_loop():
    """Background task: tick the simulation every N seconds."""
    global _sim_running
    _sim_running = True
    logger.info(f"Simulation loop started (interval: {settings.SIMULATION_INTERVAL_SECONDS}s)")
    while _sim_running:
        try:
            if telemetry_service.is_running:
                telemetry_service.tick()
        except Exception as e:
            logger.error(f"Simulation tick error: {e}")
        await asyncio.sleep(settings.SIMULATION_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup / shutdown."""
    global _sim_task

    # ── Database setup ────────────────────────────────────────────────────
    os.makedirs("./data/chroma_db", exist_ok=True)
    os.makedirs("./logs", exist_ok=True)

    try:
        from backend.database.connection import create_tables, SessionLocal
        create_tables()
        logger.info("Database tables created / verified.")

        # Wire DB into TelemetryService
        telemetry_service.configure_db(SessionLocal)

        # Seed machine rows + sample readings
        from backend.simulation.seed_data import run_all_seeds
        with SessionLocal() as db:
            run_all_seeds(db, sample_ticks=30)
        logger.info("Database seeding complete.")
    except Exception as e:
        logger.error(f"DB init error: {e}")

    # ── RAG pipeline ──────────────────────────────────────────────────────
    logger.info("Initializing RAG pipeline...")
    try:
        get_rag_pipeline().initialize()
        logger.info("RAG pipeline ready.")
    except Exception as e:
        logger.error(f"RAG pipeline init error: {e}")

    # ── Prime telemetry ───────────────────────────────────────────────────
    telemetry_service.start()
    telemetry_service.tick()

    # ── Start simulation loop ─────────────────────────────────────────────
    if settings.SIMULATION_ENABLED:
        _sim_task = asyncio.create_task(_simulation_loop())

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────
    global _sim_running
    _sim_running = False
    telemetry_service.stop()
    if _sim_task:
        _sim_task.cancel()
        try:
            await _sim_task
        except asyncio.CancelledError:
            pass
    logger.info("SAFEGUARD AI backend shutdown complete.")


app = FastAPI(
    title="SAFEGUARD AI",
    description="AI-Powered Mechanical Safety Compliance Advisor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Request/Response Models
# ─────────────────────────────────────────────────────────────────────────────

class WhatIfRequest(BaseModel):
    machine_id: str
    temperature: Optional[float] = None
    vibration: Optional[float] = None
    rpm: Optional[float] = None
    pressure: Optional[float] = None
    load: Optional[float] = None
    guard_status: Optional[bool] = None
    interlock_active: Optional[bool] = None
    emergency_stop: Optional[bool] = None
    door_locked: Optional[bool] = None
    maintenance_overdue: Optional[bool] = None


class RAGQueryRequest(BaseModel):
    query: str
    machine_type: Optional[str] = None
    top_k: int = Field(default=5, ge=1, le=20)


class ScenarioOverride(BaseModel):
    machine_id: str
    scenario: str  # any value from INJECTABLE_SCENARIOS
    degradation: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class FaultInjectRequest(BaseModel):
    machine_id: str
    scenario: str
    degradation: Optional[float] = Field(default=None, ge=0.0, le=1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Health & Status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    rag = get_rag_pipeline()
    return {
        "status": "ok",
        "version": "1.0.0",
        "simulation_running": _sim_running,
        "ibm_watsonx_configured": settings.ibm_configured,
        "langflow_configured": settings.langflow_configured,
        "rag_mode": rag._embedding_service.mode if rag._initialized else "not_initialized",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Facility Overview
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/facility/summary")
async def get_facility_summary():
    """Overall facility safety score, machine counts, alert counts."""
    return telemetry_service.get_facility_summary()


@app.get("/api/v1/facility/machines")
async def get_all_machines():
    """Configuration and current state for all machines."""
    configs = telemetry_service.get_all_machine_configs()
    states = telemetry_service.get_current_state()
    result = []
    for cfg in configs:
        mid = cfg["machine_id"]
        state = states.get(mid, {})
        result.append({**cfg, **state})
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Machine Telemetry
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/machines/current")
async def get_all_current_telemetry():
    """Current telemetry + risk score for all machines."""
    return telemetry_service.get_current_state()


@app.get("/api/v1/machines/{machine_id}/current")
async def get_machine_current(machine_id: str):
    """Current state for a single machine."""
    state = telemetry_service.get_machine_state(machine_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return state


@app.get("/api/v1/machines/{machine_id}/history")
async def get_machine_history(
    machine_id: str,
    n: int = Query(default=100, ge=1, le=500),
):
    """Historical telemetry readings for a machine."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return telemetry_service.get_history(machine_id, n)


@app.get("/api/v1/machines/{machine_id}/config")
async def get_machine_config(machine_id: str):
    """Machine configuration and thresholds."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    configs = telemetry_service.get_all_machine_configs()
    for c in configs:
        if c["machine_id"] == machine_id:
            return c
    raise HTTPException(status_code=404, detail=f"Machine config not found")


# ─────────────────────────────────────────────────────────────────────────────
# Full Machine Analysis (Multi-Agent)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/machines/{machine_id}/analysis")
async def get_machine_analysis(machine_id: str, background_tasks: BackgroundTasks):
    """
    Full multi-agent safety analysis for a machine.
    Returns risk assessment, compliance checks, recommendations, and RAG evidence.
    """
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    # Return cached if available
    cached = telemetry_service.get_cached_analysis(machine_id)
    if cached:
        # Refresh in background for next call
        background_tasks.add_task(_refresh_analysis, machine_id)
        return cached

    # Run synchronously on first call
    try:
        return telemetry_service.run_full_analysis(machine_id)
    except Exception as e:
        logger.error(f"Analysis error for {machine_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _refresh_analysis(machine_id: str):
    """Background refresh of cached analysis."""
    try:
        telemetry_service.run_full_analysis(machine_id)
    except Exception as e:
        logger.warning(f"Background analysis refresh failed for {machine_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Risk Analysis
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/risk/overview")
async def get_risk_overview():
    """Risk scores and levels for all machines."""
    states = telemetry_service.get_current_state()
    return [
        {
            "machine_id": mid,
            "machine_name": s.get("machine_name"),
            "machine_type": s.get("machine_type"),
            "risk_score": s.get("risk_score", 0),
            "risk_level": s.get("risk_level", "unknown"),
            "risk_factors": s.get("risk_factors", []),
            "risk_explanation": s.get("risk_explanation", ""),
            "anomaly_detected": s.get("anomaly_detected", False),
            "maintenance_overdue": s.get("maintenance_overdue", False),
        }
        for mid, s in states.items()
    ]


@app.get("/api/v1/risk/{machine_id}/factors")
async def get_risk_factors(machine_id: str):
    """Detailed risk factor breakdown for a machine."""
    state = telemetry_service.get_machine_state(machine_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return {
        "machine_id": machine_id,
        "risk_score": state.get("risk_score"),
        "risk_level": state.get("risk_level"),
        "risk_factors": state.get("risk_factors", []),
        "risk_explanation": state.get("risk_explanation"),
        "anomaly_detected": state.get("anomaly_detected"),
        "anomaly_score": state.get("anomaly_score"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Compliance
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/compliance/{machine_id}")
async def get_compliance(machine_id: str):
    """Compliance check results for a machine."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    analysis = telemetry_service.get_cached_analysis(machine_id)
    if analysis:
        return {
            "machine_id": machine_id,
            "compliance_score": analysis.get("compliance_score"),
            "overall_compliance_status": analysis.get("overall_compliance_status"),
            "checks": analysis.get("compliance_results", []),
        }

    # Run quick compliance check from current state
    state = telemetry_service.get_machine_state(machine_id) or telemetry_service.tick().get(machine_id, {})
    machine_type = MACHINE_CONFIGS[machine_id]["machine_type"]
    from backend.compliance.engine import compliance_engine
    checks = compliance_engine.run_compliance_check(
        machine_id=machine_id,
        machine_type=machine_type,
        temperature=state.get("temperature", 0),
        vibration=state.get("vibration", 0),
        pressure=state.get("pressure", 0),
        guard_status=state.get("guard_status", True),
        interlock_active=state.get("interlock_active", True),
        emergency_stop=state.get("emergency_stop", False),
        maintenance_overdue=state.get("maintenance_overdue", False),
    )
    return {
        "machine_id": machine_id,
        "compliance_score": compliance_engine.compliance_score(checks),
        "overall_compliance_status": compliance_engine.overall_status(checks),
        "checks": [
            {
                "check_id": c.check_id,
                "requirement": c.requirement,
                "current_condition": c.current_condition,
                "expected_condition": c.expected_condition,
                "status": c.status,
                "risk_level": c.risk_level,
                "evidence": c.evidence,
                "source": c.source,
                "explanation": c.explanation,
                "evidence_type": c.evidence_type,
                "standard_reference": c.standard_reference,
            }
            for c in checks
        ],
    }


@app.get("/api/v1/compliance/overview/all")
async def get_compliance_overview():
    """Compliance status summary for all machines."""
    results = []
    for machine_id in MACHINE_CONFIGS:
        state = telemetry_service.get_machine_state(machine_id) or {}
        machine_type = MACHINE_CONFIGS[machine_id]["machine_type"]
        from backend.compliance.engine import compliance_engine
        checks = compliance_engine.run_compliance_check(
            machine_id=machine_id,
            machine_type=machine_type,
            temperature=state.get("temperature", 20),
            vibration=state.get("vibration", 0),
            pressure=state.get("pressure", 0),
            guard_status=state.get("guard_status", True),
            interlock_active=state.get("interlock_active", True),
            emergency_stop=state.get("emergency_stop", False),
            maintenance_overdue=state.get("maintenance_overdue", False),
        )
        results.append({
            "machine_id": machine_id,
            "machine_name": MACHINE_CONFIGS[machine_id]["name"],
            "compliance_score": compliance_engine.compliance_score(checks),
            "overall_compliance_status": compliance_engine.overall_status(checks),
            "violations": sum(1 for c in checks if c.status == "non_compliant"),
            "warnings": sum(1 for c in checks if c.status == "partially_compliant"),
        })
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Recommendations
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/recommendations/{machine_id}")
async def get_recommendations(machine_id: str):
    """Safety recommendations for a machine."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    analysis = telemetry_service.get_cached_analysis(machine_id)
    if analysis:
        return analysis.get("recommendations", [])

    # Generate on demand
    try:
        result = telemetry_service.run_full_analysis(machine_id)
        return result.get("recommendations", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/recommendations/all/priority")
async def get_all_recommendations():
    """All recommendations across all machines, sorted by priority."""
    all_recs = []
    for machine_id in MACHINE_CONFIGS:
        analysis = telemetry_service.get_cached_analysis(machine_id)
        if analysis:
            for rec in analysis.get("recommendations", []):
                rec["machine_name"] = MACHINE_CONFIGS[machine_id]["name"]
                all_recs.append(rec)
    all_recs.sort(key=lambda r: (r.get("priority", 99), r.get("severity", "low")))
    return all_recs


# ─────────────────────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/alerts")
async def get_alerts():
    """Current active alerts across all machines."""
    states = telemetry_service.get_current_state()
    alerts = []
    for mid, state in states.items():
        risk = state.get("risk_score", 0)
        if risk > 80:
            alerts.append({
                "machine_id": mid,
                "machine_name": state.get("machine_name"),
                "severity": "critical",
                "title": f"CRITICAL: {state.get('machine_name')} at risk score {risk}",
                "message": state.get("risk_explanation", ""),
                "risk_score": risk,
                "timestamp": state.get("timestamp"),
            })
        elif risk > 60:
            alerts.append({
                "machine_id": mid,
                "machine_name": state.get("machine_name"),
                "severity": "high",
                "title": f"HIGH RISK: {state.get('machine_name')} at risk score {risk}",
                "message": state.get("risk_explanation", ""),
                "risk_score": risk,
                "timestamp": state.get("timestamp"),
            })
        elif risk > 40:
            alerts.append({
                "machine_id": mid,
                "machine_name": state.get("machine_name"),
                "severity": "warning",
                "title": f"ELEVATED: {state.get('machine_name')} at risk score {risk}",
                "message": state.get("risk_explanation", ""),
                "risk_score": risk,
                "timestamp": state.get("timestamp"),
            })

        # Guard-specific alerts
        if not state.get("guard_status", True):
            alerts.append({
                "machine_id": mid,
                "machine_name": state.get("machine_name"),
                "severity": "critical",
                "title": f"GUARD OPEN: {state.get('machine_name')}",
                "message": "Machine guard is open or removed. Operator at risk.",
                "risk_score": risk,
                "timestamp": state.get("timestamp"),
            })

        if state.get("emergency_stop"):
            alerts.append({
                "machine_id": mid,
                "machine_name": state.get("machine_name"),
                "severity": "critical",
                "title": f"E-STOP ACTIVE: {state.get('machine_name')}",
                "message": "Emergency stop is active. Investigate before restart.",
                "risk_score": risk,
                "timestamp": state.get("timestamp"),
            })

    alerts.sort(key=lambda a: {"critical": 0, "high": 1, "warning": 2, "info": 3}.get(a["severity"], 4))
    return alerts


# ─────────────────────────────────────────────────────────────────────────────
# RAG Evidence
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/rag/query")
async def query_rag(request: RAGQueryRequest):
    """Query the RAG pipeline for safety evidence."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    rag = get_rag_pipeline()
    try:
        chunks = rag.retrieve(
            request.query,
            machine_type=request.machine_type,
            top_k=request.top_k,
        )
        if not chunks:
            return {
                "query": request.query,
                "results": [],
                "message": "Insufficient evidence to verify this requirement.",
            }
        return {
            "query": request.query,
            "results": [
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "title": c.title,
                    "source": c.source,
                    "section": c.section,
                    "topic": c.topic,
                    "content": c.content,
                    "relevance_score": c.relevance_score,
                    "evidence_type": c.evidence_type,
                }
                for c in chunks
            ],
        }
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/rag/documents")
async def list_documents():
    """List all safety documents in the knowledge base (built-in + uploaded)."""
    from backend.rag.safety_documents import SAFETY_DOCUMENTS
    from backend.rag.document_ingestion import DocumentIngestionService
    from backend.database.connection import SessionLocal

    builtin = [
        {
            "doc_id": d["doc_id"],
            "title": d["title"],
            "document_type": d["document_type"],
            "source": d["source"],
            "machine_categories": d.get("machine_categories", []),
            "topics": d.get("topics", []),
            "chunk_count": len(d.get("chunks", [])),
            "storage": "built-in",
        }
        for d in SAFETY_DOCUMENTS
    ]

    rag = get_rag_pipeline()
    try:
        svc = DocumentIngestionService(rag, SessionLocal)
        uploaded = [
            doc for doc in svc.list_ingested_documents()
            if doc["doc_id"] not in {d["doc_id"] for d in SAFETY_DOCUMENTS}
        ]
    except Exception:
        uploaded = []

    return {"built_in": builtin, "uploaded": uploaded, "total": len(builtin) + len(uploaded)}


class DocumentUploadTextRequest(BaseModel):
    title: str
    source: str
    content: str
    document_type: str = "standard"
    machine_categories: Optional[List[str]] = None
    topics: Optional[List[str]] = None
    doc_id: Optional[str] = None


@app.post("/api/v1/rag/documents/upload/text")
async def upload_document_text(request: DocumentUploadTextRequest):
    """
    Ingest a safety document provided as raw text.
    Chunks, auto-tags, embeds, and indexes it for RAG retrieval.
    NEVER fabricates regulations — only returns what was in the uploaded document.
    """
    if not request.content.strip():
        raise HTTPException(status_code=400, detail="Document content is empty")
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Document title is required")
    try:
        from backend.rag.document_ingestion import DocumentIngestionService
        from backend.database.connection import SessionLocal
        rag = get_rag_pipeline()
        svc = DocumentIngestionService(rag, SessionLocal)
        result = svc.ingest_text(
            text=request.content,
            title=request.title,
            source=request.source,
            document_type=request.document_type,
            machine_categories=request.machine_categories,
            topics=request.topics,
            doc_id=request.doc_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Document upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/rag/documents/upload/file")
async def upload_document_file(
    file: UploadFile = File(...),
    title: str = Query(default=""),
    source: str = Query(default="Uploaded Document"),
    document_type: str = Query(default="standard"),
    machine_categories: str = Query(default=""),
):
    """
    Upload a PDF, TXT, or DOCX safety document file.
    The file is saved temporarily, extracted, chunked, and indexed.
    """
    import tempfile
    from backend.rag.document_ingestion import DocumentIngestionService
    from backend.database.connection import SessionLocal
    from pathlib import Path as _Path

    allowed_extensions = {".pdf", ".txt", ".docx", ".doc"}
    filename = getattr(file, "filename", "") or ""
    suffix = _Path(filename).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Allowed: pdf, txt, docx",
        )
    try:
        contents = await file.read()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        cats = [c.strip() for c in machine_categories.split(",") if c.strip()] or None
        effective_title = title or _Path(filename).stem

        rag = get_rag_pipeline()
        svc = DocumentIngestionService(rag, SessionLocal)
        result = svc.ingest_file(
            file_path=tmp_path,
            title=effective_title,
            source=source,
            document_type=document_type,
            machine_categories=cats,
        )
        os.unlink(tmp_path)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/v1/rag/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Remove an uploaded document from the RAG knowledge base."""
    from backend.rag.document_ingestion import DocumentIngestionService
    from backend.database.connection import SessionLocal
    from backend.rag.safety_documents import SAFETY_DOCUMENTS as _BUILTIN

    if doc_id in {d["doc_id"] for d in _BUILTIN}:
        raise HTTPException(status_code=403, detail="Cannot delete built-in safety standards.")
    rag = get_rag_pipeline()
    svc = DocumentIngestionService(rag, SessionLocal)
    removed = svc.delete_document(doc_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return {"message": f"Document '{doc_id}' deleted successfully."}


@app.get("/api/v1/rag/documents/{doc_id}")
async def get_document_details(doc_id: str):
    """Get metadata and chunk previews for a specific document."""
    from backend.rag.safety_documents import SAFETY_DOCUMENTS as _BUILTIN
    for d in _BUILTIN:
        if d["doc_id"] == doc_id:
            return {
                "doc_id": d["doc_id"],
                "title": d["title"],
                "source": d["source"],
                "document_type": d["document_type"],
                "machine_categories": d.get("machine_categories", []),
                "topics": d.get("topics", []),
                "chunks": [
                    {"section": c["section"], "topic": c["topic"],
                     "preview": c["content"][:200]}
                    for c in d.get("chunks", [])
                ],
                "storage": "built-in",
            }
    rag = get_rag_pipeline()
    chunks = [c for c in rag._flat_chunks if c["doc_id"] == doc_id]
    if not chunks:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return {
        "doc_id": doc_id,
        "title": chunks[0]["title"],
        "source": chunks[0]["source"],
        "document_type": chunks[0].get("document_type", "uploaded"),
        "machine_categories": chunks[0].get("machine_categories", []),
        "chunk_count": len(chunks),
        "chunks": [
            {"section": c["section"], "topic": c["topic"], "preview": c["content"][:200]}
            for c in chunks
        ],
        "storage": "memory",
    }


@app.get("/api/v1/rag/evidence/{machine_id}")
async def get_machine_evidence(machine_id: str):
    """Get RAG evidence used for the last analysis of a machine."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    analysis = telemetry_service.get_cached_analysis(machine_id)
    if not analysis:
        return {"machine_id": machine_id, "evidence": [], "message": "No analysis cached yet. Run analysis first."}
    return {
        "machine_id": machine_id,
        "evidence": analysis.get("retrieved_evidence", []),
    }


# ─────────────────────────────────────────────────────────────────────────────
# What-If Simulator
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/api/v1/whatif/simulate")
async def run_whatif(request: WhatIfRequest):
    """
    Safety What-If Simulator.
    Apply parameter overrides and get instant risk/compliance recalculation.
    Uses the same real risk engine — no LLM hallucination.
    """
    if request.machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {request.machine_id} not found")

    overrides = {
        k: v for k, v in request.model_dump().items()
        if k != "machine_id" and v is not None
    }

    try:
        return safety_orchestrator.whatif_analysis(request.machine_id, overrides)
    except Exception as e:
        logger.error(f"What-If error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/whatif/baseline/{machine_id}")
async def get_whatif_baseline(machine_id: str):
    """Get baseline values for the What-If simulator."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    cfg = MACHINE_CONFIGS[machine_id]
    thresholds = cfg["thresholds"]
    return {
        "machine_id": machine_id,
        "machine_name": cfg["name"],
        "baseline": cfg["base"],
        "thresholds": {k: getattr(thresholds, k) for k in thresholds.__dataclass_fields__},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Simulation Controls  (Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/simulation/status")
async def get_simulation_status():
    """Overall simulation status and per-machine scenario summary."""
    statuses = telemetry_service.get_all_machine_statuses()
    return {
        "simulation_running": telemetry_service.is_running,
        "machines": statuses,
        "available_scenarios": INJECTABLE_SCENARIOS,
        "scenario_labels": SCENARIO_LABELS,
    }


@app.post("/api/v1/simulation/start")
async def start_simulation():
    """Start the simulation tick loop."""
    telemetry_service.start()
    return {"message": "Simulation started", "running": telemetry_service.is_running}


@app.post("/api/v1/simulation/stop")
async def stop_simulation():
    """Pause the simulation tick loop (readings freeze)."""
    telemetry_service.stop()
    return {"message": "Simulation stopped", "running": telemetry_service.is_running}


@app.post("/api/v1/simulation/fault")
async def inject_fault(req: FaultInjectRequest):
    """
    Inject a fault scenario onto a specific machine.

    Available scenarios: normal, degrading, overheating, excessive_vibration,
    excessive_pressure, overload, guard_interlock_failure, maintenance_overdue,
    sensor_anomaly, anomaly, critical, maintenance
    """
    if req.machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {req.machine_id} not found")
    if req.scenario not in INJECTABLE_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario '{req.scenario}'. Valid: {INJECTABLE_SCENARIOS}",
        )
    state = telemetry_service.inject_fault(req.machine_id, req.scenario, req.degradation)
    return {
        "message": f"Fault '{req.scenario}' injected on {req.machine_id}",
        "scenario_label": SCENARIO_LABELS.get(req.scenario, req.scenario),
        "machine_id": req.machine_id,
        "risk_score": state.get("risk_score"),
        "risk_level": state.get("risk_level"),
        "machine_status": state.get("machine_status"),
    }


@app.post("/api/v1/simulation/reset/{machine_id}")
async def reset_machine(machine_id: str):
    """Reset a machine to normal operating state."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    state = telemetry_service.reset_machine(machine_id)
    return {
        "message": f"Machine {machine_id} reset to normal",
        "machine_id": machine_id,
        "risk_score": state.get("risk_score"),
        "machine_status": state.get("machine_status"),
    }


@app.post("/api/v1/simulation/maintenance/{machine_id}/acknowledge")
async def acknowledge_maintenance(machine_id: str):
    """Acknowledge that maintenance has been performed; resets operating hours."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    state = telemetry_service.acknowledge_maintenance(machine_id)
    return {
        "message": f"Maintenance acknowledged for {machine_id}",
        "machine_id": machine_id,
        "operating_hours": state.get("operating_hours", 0),
        "maintenance_overdue": state.get("maintenance_overdue", False),
    }


@app.get("/api/v1/simulation/scenarios")
async def list_scenarios():
    """List all available fault scenarios with descriptions."""
    return [
        {"scenario": s, "label": SCENARIO_LABELS.get(s, s)}
        for s in INJECTABLE_SCENARIOS
    ]


@app.get("/api/v1/machines/{machine_id}/status")
async def get_machine_status(machine_id: str):
    """Rich machine status: scenario, degradation, operating hours, risk."""
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")
    return telemetry_service.get_machine_status(machine_id)


@app.get("/api/v1/machines/status/all")
async def get_all_machine_statuses():
    """Status for every machine."""
    return telemetry_service.get_all_machine_statuses()


@app.get("/api/v1/machines/{machine_id}/history/db")
async def get_machine_history_db(
    machine_id: str,
    limit: int = Query(default=100, ge=1, le=1000),
    since: Optional[str] = Query(default=None, description="ISO datetime filter"),
):
    """
    Historical telemetry readings from the SQL database.
    Falls back to in-memory if DB is unavailable.
    """
    if machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'since' datetime format")

    return telemetry_service.get_history_from_db(machine_id, limit=limit, since=since_dt)


# Kept for backward compatibility with existing frontend
@app.post("/api/v1/simulation/scenario")
async def set_scenario(override: ScenarioOverride):
    """Force a simulation scenario (backward-compat alias for /fault)."""
    if override.scenario not in INJECTABLE_SCENARIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scenario. Valid: {INJECTABLE_SCENARIOS}",
        )
    if override.machine_id not in MACHINE_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Machine {override.machine_id} not found")

    telemetry_service.force_scenario(override.machine_id, override.scenario, override.degradation)
    return {"message": f"Scenario '{override.scenario}' applied to {override.machine_id}"}


@app.get("/api/v1/simulation/tick")
async def manual_tick():
    """Manually trigger a simulation tick (useful for testing)."""
    result = telemetry_service.tick()
    return {"ticked": True, "machines": list(result.keys())}


# ─────────────────────────────────────────────────────────────────────────────
# IBM Integration Status
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/api/v1/ibm/status")
async def get_ibm_status():
    """Status of IBM service integrations."""
    rag = get_rag_pipeline()
    return {
        "watsonx": {
            "configured": settings.ibm_configured,
            "available": settings.ibm_configured,
            "model": settings.IBM_LLM_MODEL_ID if settings.ibm_configured else None,
            "embedding_model": settings.IBM_EMBEDDING_MODEL_ID if settings.ibm_configured else None,
            "url": settings.IBM_WATSONX_URL,
        },
        "langflow": {
            "configured": settings.langflow_configured,
            "base_url": settings.LANGFLOW_BASE_URL,
            "rag_flow_id": settings.LANGFLOW_FLOW_ID_RAG or "not configured",
            "agent_flow_id": settings.LANGFLOW_FLOW_ID_AGENT or "not configured",
        },
        "orchestrate": {
            "configured": bool(settings.IBM_ORCHESTRATE_API_KEY),
            "instance_url": settings.IBM_ORCHESTRATE_INSTANCE_URL or "not configured",
        },
        "rag": {
            "mode": rag._embedding_service.mode if rag._initialized else "not_initialized",
            "initialized": rag._initialized,
            "document_count": len(rag._flat_chunks),
        },
    }
